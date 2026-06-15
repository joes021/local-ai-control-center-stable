import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type CustomSelectOption = {
  value: string;
  label: string;
};

type CustomSelectProps = {
  value: string;
  options: CustomSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
};

type CustomSelectMenuPosition = {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
};

export function CustomSelect({
  value,
  options,
  onChange,
  placeholder = "Izaberi",
  ariaLabel,
}: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<CustomSelectMenuPosition | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const selectedOption = useMemo(
    () => options.find((option) => option.value === value) ?? null,
    [options, value],
  );

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setMenuPosition(null);
      return;
    }

    function updateMenuPosition() {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }

      const viewportPadding = 12;
      const estimatedHeight = Math.min(360, options.length * 52 + 20);
      const width = Math.min(rect.width, window.innerWidth - viewportPadding * 2);
      const left = Math.min(
        Math.max(viewportPadding, rect.left),
        Math.max(viewportPadding, window.innerWidth - width - viewportPadding),
      );
      const belowSpace = Math.max(0, window.innerHeight - rect.bottom - viewportPadding);
      const aboveSpace = Math.max(0, rect.top - viewportPadding);
      const renderAbove =
        belowSpace < Math.min(estimatedHeight, 220) && aboveSpace > belowSpace;
      const availableSpace = Math.max(96, (renderAbove ? aboveSpace : belowSpace) - 8);
      const maxHeight = Math.min(estimatedHeight, availableSpace);
      const unclampedTop = renderAbove ? rect.top - maxHeight - 8 : rect.bottom + 8;
      const top = Math.min(
        Math.max(viewportPadding, unclampedTop),
        Math.max(viewportPadding, window.innerHeight - maxHeight - viewportPadding),
      );

      setMenuPosition({ top, left, width, maxHeight });
    }

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, options.length, value]);

  const menu =
    open && menuPosition
      ? createPortal(
          <div
            ref={menuRef}
            className="custom-select-menu custom-select-menu-portal"
            role="listbox"
            aria-label={ariaLabel}
            style={{
              top: `${menuPosition.top}px`,
              left: `${menuPosition.left}px`,
              width: `${menuPosition.width}px`,
              maxHeight: `${menuPosition.maxHeight}px`,
            }}
          >
            {options.map((option) => {
              const selected = option.value === value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`custom-select-option${selected ? " custom-select-option-selected" : ""}`}
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                >
                  <span className="custom-select-option-label">{option.label}</span>
                </button>
              );
            })}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <div className={`custom-select${open ? " custom-select-open" : ""}`} ref={rootRef}>
        <button
          ref={triggerRef}
          type="button"
          className="custom-select-trigger"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label={ariaLabel}
          onClick={() => setOpen((current) => !current)}
        >
          <span className="custom-select-value">{selectedOption?.label ?? placeholder}</span>
          <span className="custom-select-chevron" aria-hidden="true" />
        </button>
      </div>
      {menu}
    </>
  );
}
