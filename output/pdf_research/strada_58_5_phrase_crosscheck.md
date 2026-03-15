# Phrase Cross-Check: Transcript vs Pilot/Controller Glossary (10/12/17)

Source transcript:
- /Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/output/transcribe/strada-liviu-rebreanu-58-5/Strada Liviu Rebreanu, 58 5.consensus.md

Glossary corpus:
- /Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/output/pdf_research/pcg_10-12-17_extracted.txt

| Transcript phrase | Match status | Glossary evidence | Interpretation |
|---|---|---|---|
| "Southwest 4054" | Partial | No direct callsign example entry; glossary is term-focused. | Airline callsign+flight number is valid ATC style, but not a glossary-defined standalone term here. |
| "caution wake turbulence" | Partial | WAKE TURBULENCE definition at extracted line 9129. | Core term is directly present; the exact warning phrase "caution wake turbulence" is standard operational phraseology but not explicitly listed as an entry string in this glossary text extract. |
| "heavy Airbus 330" | Partial | AIRCRAFT CLASSES at line 563 and Heavy threshold at line 568. | "Heavy" is formally defined as a wake category; pairing with aircraft type in transmission is operationally coherent. |
| "five miles upwind" | Partial | TRAFFIC PATTERN at line 8494; Upwind Leg definition at line 8499. | "Upwind" is defined in traffic-pattern context; distance qualifier "five miles" is plausible ATC usage but not a separate glossary term. |
| "wind 120 at 5" | Not explicit in glossary | No exact wind readout phrase found in matched entries. | The format is standard in ATC weather delivery, but this glossary extract does not provide a direct phrase template for this specific pattern. |
| "Runway 27 cleared for takeoff" | Exact (core clearance) + Partial (runway number) | CLEARED FOR TAKEOFF at line 1941; RUNWAY definition at line 6949. | Core clearance phrase is exact and authoritative; runway-number insertion is expected operationally. |
| "Runway 27 cleared for takeoff, Southwest 4054" (readback) | Exact (readback concept) + Partial (full sentence form) | READ BACK at line 6726; CLEARED FOR TAKEOFF at line 1941. | Readback behavior is explicitly defined and matches transcript structure. |

## Overall assessment
- Your transcript aligns strongly with FAA glossary semantics.
- Highest-confidence standardized elements in this clip are:
  - "cleared for takeoff"
  - "wake turbulence"
  - readback structure
- Medium-confidence elements are numerical/acoustic items (callsign digits, aircraft model digits) rather than phraseology structure.
