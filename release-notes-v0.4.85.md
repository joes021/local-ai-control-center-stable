# RuntimePilot v0.4.85

- popravljeno beskonačno/ponovljeno startovanje panela koje je moglo da izazove lavinu `cmd` prozora
- desktop i Start Menu `RuntimePilot` prečice sada otvaraju skriveni `Open-Control-Center.vbs` launcher umesto vidljivog `.cmd` toka
- Windows launcher sada proverava i `health` i da li je pokretanje već u toku pre nego što pokuša novi start
- python fallback start je vraćen na pouzdaniji skriveni `python.exe` tok umesto `pythonw.exe`, što sprečava tihi neuspeh panela
