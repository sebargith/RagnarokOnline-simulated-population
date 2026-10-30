# Graphical client download verification

Downloaded 2026-10-30 using the user's supplied GitHub and MediaFire folders.
Active files: `D:/Ragnarok Agents/runtime/player-client` (ignored by Git).
Original downloads, public folder metadata, extracted supporting files and
NEMO are retained in `runtime/player-client-downloads` in the primary workspace.
No downloaded executable, installer, server or driver was executed.

## Verified

- GitHub `MegamiNoBisho/UnpackedkROclients` archive
  `2013-08-07aRagexe.7z`: SHA-256
  `929dc940528b208e365a364cc958bbc4ec2f7c8ac0b0aee87c5248d0ab63af92`.
- Extracted original EXE SHA-256
  `1ad56447664d43adb6e1a51e1d59ef2df7bae1494ba839a337285986d30c04e5`
  matches MediaFire's independently listed original EXE metadata.
- Matching ready-made RAR: 186,834,382 bytes; SHA-256
  `d0e2fe950b8fbea8825c6f096e0f13773d248d4d8e0174135ac8866cd2016434`.
  Selected only its client subtree; the bundled historical Hercules server
  was not installed. Patched EXE hash
  `e077bad125c48b5c354d46e7ccf1d77b5ec859d781351fb24b418d5c5602aa5a`
  matches the separately listed patched EXE metadata.
- Both EXEs have valid PE32 x86 headers and COFF timestamp
  `2013-08-06T01:38:25Z`. Their August 7 version label comes from the matching
  archive/listing, not that timestamp alone. Protocol login is not yet verified.
- Downloaded all nine `data.partNN.rar` volumes, `rdata.grf`, and all seven
  October 14 supporting-file volumes. Every downloaded file matched its
  MediaFire metadata SHA-256. Both multipart sets extracted without errors.
- Parsed `data.grf` version 0x200: 54,473 entries, including
  `data/prontera.gat`, `data/prontera.gnd`, `data/prontera.rsw` (GRF paths use
  backslashes). Required maps are present; rendering is not yet tested.
- Copied supporting DLLs/manifests, audio plugins, BGM, System and AI files.
  All 24 direct PE imports resolve to local files or Windows SysWOW64 files.
  Transitive dependencies and actual loading have not been tested.
- NEMO source/tool download pinned to `8397342aa780f969ffa67aed7b7eeda36dd1d4ce`.
  Its README identifies this repository as historical and directs current
  development to GitLab `4144/Nemo`. No patches were applied.

Local `player-client/DOWNLOAD_VERIFICATION.json` records selected executable,
GRF hashes/sizes, direct DLL imports and `graphical_login_verified: false`.
Source-provided hashes establish download integrity, not publisher authenticity.
The redundant DepositFiles alternative and unrelated dated clients were not needed.

## Next action

Inspect the ready-made client's embedded connection configuration and patches,
configure loopback login for the project's existing server, create a separate
player account, then verify graphical login and Prontera rendering. Assets are
staged; the package's existing configuration is not a verified project launcher.
Game services, existing accounts and models were not modified by this download.
