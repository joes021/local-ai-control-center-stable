from __future__ import annotations

from pathlib import Path
import struct


_IGNORED_SYSTEM_DLLS = frozenset(
    {
        "advapi32.dll",
        "bcrypt.dll",
        "cfgmgr32.dll",
        "combase.dll",
        "comctl32.dll",
        "comdlg32.dll",
        "crypt32.dll",
        "dnsapi.dll",
        "gdi32.dll",
        "imm32.dll",
        "iphlpapi.dll",
        "kernel32.dll",
        "mpr.dll",
        "msimg32.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "mswsock.dll",
        "normaliz.dll",
        "ntdll.dll",
        "ole32.dll",
        "oleaut32.dll",
        "powrprof.dll",
        "psapi.dll",
        "rpcrt4.dll",
        "secur32.dll",
        "setupapi.dll",
        "shell32.dll",
        "shlwapi.dll",
        "ucrtbase.dll",
        "user32.dll",
        "userenv.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "version.dll",
        "winhttp.dll",
        "wininet.dll",
        "winmm.dll",
        "ws2_32.dll",
    }
)
_IGNORED_SYSTEM_PREFIXES = ("api-ms-win-", "ext-ms-win-")
_FILE_HEADER_SIZE = 20
_SECTION_HEADER_SIZE = 40
_IMPORT_DIRECTORY_INDEX = 1
_DELAY_IMPORT_DIRECTORY_INDEX = 13


def detect_missing_sidecar_imports(binary_path: Path) -> tuple[str, ...]:
    if not binary_path.is_file():
        return ()

    try:
        payload = binary_path.read_bytes()
    except OSError:
        return ()

    pe_info = _parse_pe_headers(payload)
    if pe_info is None:
        return ()

    imported_names = _collect_import_names(payload, pe_info)
    missing: list[str] = []
    for dll_name in imported_names:
        normalized = dll_name.lower()
        if _is_ignored_system_dll(normalized):
            continue
        if not (binary_path.parent / dll_name).is_file():
            missing.append(dll_name)
    return tuple(dict.fromkeys(missing))


def _parse_pe_headers(payload: bytes) -> dict[str, object] | None:
    try:
        if payload[:2] != b"MZ":
            return None
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        if payload[pe_offset : pe_offset + 4] != b"PE\x00\x00":
            return None
        coff_offset = pe_offset + 4
        number_of_sections = struct.unpack_from("<H", payload, coff_offset + 2)[0]
        size_of_optional_header = struct.unpack_from("<H", payload, coff_offset + 16)[0]
        optional_offset = coff_offset + _FILE_HEADER_SIZE
        optional_magic = struct.unpack_from("<H", payload, optional_offset)[0]
    except (struct.error, IndexError):
        return None

    if optional_magic == 0x10B:
        data_directories_offset = optional_offset + 96
    elif optional_magic == 0x20B:
        data_directories_offset = optional_offset + 112
    else:
        return None

    section_headers_offset = optional_offset + size_of_optional_header
    sections: list[dict[str, int]] = []
    try:
        for index in range(number_of_sections):
            section_offset = section_headers_offset + (index * _SECTION_HEADER_SIZE)
            virtual_size = struct.unpack_from("<I", payload, section_offset + 8)[0]
            virtual_address = struct.unpack_from("<I", payload, section_offset + 12)[0]
            raw_size = struct.unpack_from("<I", payload, section_offset + 16)[0]
            raw_pointer = struct.unpack_from("<I", payload, section_offset + 20)[0]
            sections.append(
                {
                    "virtual_size": virtual_size,
                    "virtual_address": virtual_address,
                    "raw_size": raw_size,
                    "raw_pointer": raw_pointer,
                }
            )
    except (struct.error, IndexError):
        return None

    return {
        "payload": payload,
        "sections": tuple(sections),
        "data_directories_offset": data_directories_offset,
    }


def _collect_import_names(payload: bytes, pe_info: dict[str, object]) -> tuple[str, ...]:
    names: list[str] = []
    names.extend(_collect_standard_import_names(payload, pe_info))
    names.extend(_collect_delay_import_names(payload, pe_info))
    return tuple(names)


def _collect_standard_import_names(
    payload: bytes,
    pe_info: dict[str, object],
) -> tuple[str, ...]:
    directory = _read_data_directory(pe_info, _IMPORT_DIRECTORY_INDEX)
    if directory is None:
        return ()

    import_offset = _rva_to_offset(directory["rva"], pe_info)
    if import_offset is None:
        return ()

    names: list[str] = []
    current_offset = import_offset
    while current_offset + 20 <= len(payload):
        try:
            descriptor = struct.unpack_from("<LLLLL", payload, current_offset)
        except struct.error:
            break
        if descriptor == (0, 0, 0, 0, 0):
            break
        name_rva = descriptor[3]
        name = _read_ascii_at_rva(payload, pe_info, name_rva)
        if name:
            names.append(name)
        current_offset += 20
    return tuple(names)


def _collect_delay_import_names(
    payload: bytes,
    pe_info: dict[str, object],
) -> tuple[str, ...]:
    directory = _read_data_directory(pe_info, _DELAY_IMPORT_DIRECTORY_INDEX)
    if directory is None:
        return ()

    delay_offset = _rva_to_offset(directory["rva"], pe_info)
    if delay_offset is None:
        return ()

    names: list[str] = []
    current_offset = delay_offset
    while current_offset + 32 <= len(payload):
        try:
            descriptor = struct.unpack_from("<LLLLLLLL", payload, current_offset)
        except struct.error:
            break
        if descriptor == (0, 0, 0, 0, 0, 0, 0, 0):
            break
        attributes, name_pointer = descriptor[0], descriptor[1]
        name_rva = name_pointer if attributes in (0, 1) else 0
        name = _read_ascii_at_rva(payload, pe_info, name_rva)
        if name:
            names.append(name)
        current_offset += 32
    return tuple(names)


def _read_data_directory(
    pe_info: dict[str, object],
    index: int,
) -> dict[str, int] | None:
    payload = pe_info["payload"]
    data_directories_offset = int(pe_info["data_directories_offset"])
    directory_offset = data_directories_offset + (index * 8)
    try:
        rva, size = struct.unpack_from("<LL", payload, directory_offset)
    except struct.error:
        return None
    if rva == 0 or size == 0:
        return None
    return {"rva": rva, "size": size}


def _read_ascii_at_rva(
    payload: bytes,
    pe_info: dict[str, object],
    rva: int,
) -> str:
    if rva == 0:
        return ""
    offset = _rva_to_offset(rva, pe_info)
    if offset is None or offset >= len(payload):
        return ""
    end = payload.find(b"\x00", offset)
    if end == -1:
        end = len(payload)
    return payload[offset:end].decode("utf-8", errors="ignore").strip()


def _rva_to_offset(rva: int, pe_info: dict[str, object]) -> int | None:
    for section in pe_info["sections"]:
        virtual_address = section["virtual_address"]
        section_size = max(section["virtual_size"], section["raw_size"])
        if virtual_address <= rva < virtual_address + section_size:
            return section["raw_pointer"] + (rva - virtual_address)
    if 0 <= rva < len(pe_info["payload"]):
        return rva
    return None


def _is_ignored_system_dll(normalized_name: str) -> bool:
    return normalized_name in _IGNORED_SYSTEM_DLLS or normalized_name.startswith(
        _IGNORED_SYSTEM_PREFIXES
    )
