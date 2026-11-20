# Reference devices

The devices that performance criteria are measured on (plan §9, §11 and §17 questions 10 and 22). A device is recorded here before its first run. No serial number or owner's name is kept in this file.

## Desktop reference: the M3 Pro

Named by the owner on 15 November 2026 (plan revision 6, §17 question 22). Recorded on 15 November 2026 from `system_profiler`, `sw_vers` and Chrome itself.

| Field | Value |
|---|---|
| Model | MacBook Pro, model identifier `Mac15,6` |
| SoC | Apple M3 Pro: 11 CPU cores (5 performance, 6 efficiency), 14 GPU cores |
| RAM | 18 GB |
| OS | macOS 27.0.1 (build 26A434) |
| Browser | Google Chrome 157.0.8103.52 for the runs of 15–16 November 2026. It updated itself to 157.0.8103.79 before the runs of 17 November |
| WebGL renderer string | `ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)` |
| Built-in display | Liquid Retina XDR, 3024 × 1964 pixels, set to 1512 × 982 (pixel ratio 2) at 120 Hz |
| Usual external display | 3440 × 1440 at 85 Hz. Disconnected for timed runs (`lab/p1-render/prereg.md` §5.2) |

The OS and browser versions are noted again with every run, because both update themselves.

## Reference Android

**Not chosen.** The plan asks for a borrowed or owned mid-range phone, Galaxy A5x class; nothing is bought (§17 question 10). Design note question Q2 is still open. Every decision that depends on a real phone waits for it.

## Stand-in for the phone

Chrome's 6× CPU throttling on the desktop reference. It slows the main thread only and leaves the GPU, the memory and the thermal limits of a phone untouched, so it can warn early and cannot stand for a pass.
