# PoC: judge measurements

> Claude Code bulut sessiyasida olingan mo'ljal natija, rasmiy o'lchov emas: server cgroup v1, Flutter base image sessiya sharoitida apt qadamisiz yig'ilgan. Rasmiy o'lchovlar — `docs/poc.md` bo'yicha Erkinning kompyuteri va Oracle A1 serverida.

- Date: 2026-10-01 14:24 UTC
- Machine: x86_64, 4 CPUs, 15.7 GiB RAM
- System: Ubuntu 24.04.4 LTS, kernel 6.18.44-fc-v50, cgroup v1, Docker 29.6.2
- Images: ohw-base-dart:3.13.5, ohw-base-flutter:3.47.5
- Peak RAM is sampled every 0.2 s, so very short spikes can be missed.

## dart-cart (dart)

Cold build 16.8 s; teacher's solution 11.9 s, peak 467 MB. Time limit 30 s, memory limit 1024 MB, 9 tests.

| Submission | Verdict | Expected | Tests run | Total | Peak RAM |
|---|---|---|---|---|---|
| starter | wrong_answer (test 1) | ✓ | 1.3 s | 1.4 s | 247 MB |
| ok | accepted | ✓ | 1.3 s | 1.4 s | 246 MB |
| fail_logic | wrong_answer (test 3) | ✓ | 1.3 s | 1.3 s | 247 MB |
| compile_error | compile_error | ✓ | 1.3 s | 1.4 s | 222 MB |
| timeout | time_limit (test 1) | ✓ | 30.2 s | 30.3 s | 250 MB |
| memory | memory_limit (test 2) | ✓ | 5.6 s | 5.7 s | 1021 MB |
| forbidden_import | rejected | ✓ | 0.0 s | 0.0 s | — |
| spoof_attempt | wrong_answer (test 1) | ✓ | 1.4 s | 1.4 s | 244 MB |

## flutter-todo (flutter)

Cold build 26.9 s; teacher's solution 15.4 s, peak 903 MB. Time limit 90 s, memory limit 3072 MB, 9 tests.

| Submission | Verdict | Expected | Tests run | Total | Peak RAM |
|---|---|---|---|---|---|
| starter | wrong_answer (test 1) | ✓ | 3.5 s | 3.7 s | 608 MB |
| ok | accepted | ✓ | 5.8 s | 5.9 s | 682 MB |
| fail_logic | wrong_answer (test 3) | ✓ | 3.0 s | 3.1 s | 607 MB |
| fail_widget | wrong_answer (test 4) | ✓ | 4.5 s | 4.7 s | 681 MB |
| compile_error | compile_error | ✓ | 2.5 s | 2.6 s | 483 MB |
| timeout | time_limit (test 2) | ✓ | 90.2 s | 90.3 s | 628 MB |
| memory | memory_limit (test 2) | ✓ | 24.7 s | 24.8 s | 3071 MB |
| forbidden_import | rejected | ✓ | 0.0 s | 0.0 s | — |
| spoof_attempt | wrong_answer (test 2) | ✓ | 2.9 s | 3.1 s | 606 MB |

## Compile cache

The correct submission in the warm image, and with the compile cache deleted first (median of 3).

| Example | Warm cache | No cache | Speed-up |
|---|---|---|---|
| dart-cart | 1.4 s, peak 248 MB | 12.3 s, peak 523 MB | 8.8x |
| flutter-todo | 4.3 s, peak 676 MB | 12.9 s, peak 921 MB | 3.0x |

## Two slots at once

The correct submission of each, alone and both at the same time (JUDGE_SLOTS=heavy:1,fast:1); median of 3.

| Example | Alone | Together | Slowdown |
|---|---|---|---|
| flutter-todo | 4.5 s | 4.4 s | 0.97x |
| dart-cart | 1.5 s | 1.4 s | 0.95x |

## Two-stage Flutter: `dart test` inside a Flutter project

| Check | Result | Time |
|---|---|---|
| `dart test`, logic without Flutter imports (first run) | passes | 7.9 s |
| `dart test`, the same again (cache warm) | passes | 1.0 s |
| `flutter test`, the same logic test | passes | 12.1 s |
| `dart test`, logic in a file that imports Flutter | fails (exit 1) | 6.5 s |

All verdicts as expected.
