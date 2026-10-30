# Graphical client download verification

Downloaded 2026-10-30 using the user's supplied GitHub and MediaFire folders.
Active files: `D:/Ragnarok Agents/runtime/player-client` (ignored by Git).
Original downloads, public folder metadata, extracted supporting files and
NEMO are retained in `runtime/player-client-downloads` in the primary workspace.
The initial download verification did not execute downloaded programs.
Subsequent client/OpenSetup launches are recorded separately below; no bundled
historical server, installer or driver was run.

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

## Local configuration and graphical startup

Configured 2026-10-30 using retained local helper
`runtime/player-client-downloads/configure-local-player.py` (primary workspace).
An additional `local.grf` overrides only `data/clientinfo.xml`; the same XML
is supplied in the loose data folder. Endpoint: `127.0.0.1:6900`, version 45,
English langtype 1, display `Ragnarok Agents Local`. Original GRFs/EXEs remain
unchanged; `data.ini.downloaded` preserves the supplied GRF order.

Created ordinary account `roplayer` (2000020, group 0) and novice `Visitor`
at Prontera 152,180. Existing accounts/characters were not modified. Generated
credentials are only in ignored `runtime/player-client/PLAYER_ACCOUNT.txt`.
`Play-Local.cmd` launches the selected patched EXE with argument `1rag1`.
`START_HERE.txt` contains player instructions. A launch with `-1rag1` exited;
the corrected `1rag1` launch displayed the actual local-server selection
screen and artwork, observed through the computer-use skill. This confirms
basic graphics startup/configuration loading, not protocol/map compatibility.

OpenSetup was opened and its Apply button used for initial graphics settings;
the configured display was Direct3D HAL, 640x480, windowed. No system security
setting was changed. The game remains at server selection for user sign-in.
Computer-use guidance prohibits automating authentication dialogs; user login
is the remaining handoff before map rendering can be checked.

The existing continuous controller was started using the documented `start`
command for the graphical session. Check its live status before assuming the
agents remain active; no additional duration/stability claim is made.

## Next action

User: select `Ragnarok Agents Local`, sign in using the local credential file,
and select `Visitor`. Then verify Prontera rendering and nearby M4 characters.
Packet-obfuscation compatibility and successful graphical map entry remain
unverified until that step; do not infer them from server selection alone.
