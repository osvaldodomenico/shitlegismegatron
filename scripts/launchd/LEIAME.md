# Espelho no HD externo (Mac do Domenico)

- `espelho_hd.sh` copia da VPS para `/Volumes/BEE MAC/MEGATRON-2026/`: `urnas/` (rsync
  incremental), `tse/` (cadastro de locais) e `banco/` (pg_dump -Fc, com `-latest`), a cada
  30 min, validando contagem x VPS e tamanho do dump.
- **TCC do macOS**: um LaunchAgent NAO consegue ler `~/Downloads` nem escrever em
  `/Volumes/*` sem "Acesso total ao disco" para `/bin/bash`. Por isso em 04/10 o espelho
  rodou como processo desanexado (`nohup`) a partir de uma sessao com acesso, com o
  script copiado para `~/Library/Application Support/megatron/`.
- Para usar os plists: Ajustes > Privacidade e Seguranca > Acesso total ao disco > `+` >
  `/bin/bash`; depois `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.shiftworks.megatron.espelho.plist`.
- `com.shiftworks.megatron.acordado.plist` roda `caffeinate -s -i -m` (sem sono na tomada;
  tampa fechada sem monitor externo ainda dorme — para isso, `sudo pmset -a disablesleep 1`).
