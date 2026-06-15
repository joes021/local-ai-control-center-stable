# Plan: Settings + Compatibility + Benchmark home-shell

1. Dodati zajedničke helper klase za status deck i action strip da tri strane koriste isti vizuelni sistem.
2. Prepakovati `CompatibilityPage` u full-width tok bez `SecondaryActionRail`.
3. Prepakovati `BenchmarkPage` u full-width tok bez `SecondaryActionRail`.
4. Dodati vršni status deck i navigacioni action strip na `SettingsPage`.
5. Ažurirati testove koji proveravaju frontend bundle i UI tekst.
6. Pokrenuti ciljane pytest testove i browser proveru za ove tri strane.
