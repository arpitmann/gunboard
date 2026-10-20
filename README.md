# gunboard

Every keypress is a gunshot.

A small Python script that listens to your keyboard system-wide and fires a different weapon depending on what you press. No sound files are included: every shot is synthesized at startup from band-limited noise, pitch-swept sine "thumps", exponential envelopes and a simple tapped echo, all in NumPy. Shots are mixed in a real-time audio callback, so fast typing overlaps into a firefight instead of cutting each sound off.

## The arsenal

| Key | Weapon |
|---|---|
| Letters | Pump shotgun, each letter tuned slightly differently (`a` deepest, `z` brightest) |
| Numbers | 9mm pistol |
| Special characters | Sniper rifle with a rolling echo |
| Space | Silenced pistol |
| Enter | Shotgun pump reload |
| Backspace | Revolver dry-fire click |
| Tab | 3-round SMG burst |
| Caps Lock | Grenade |
| F12 | Safety on/off (mute toggle) |

Modifier and arrow keys stay silent so shortcuts don't set anything off.

## Run it

```bash
pip install numpy sounddevice pynput
python gunboard.py
```

On Windows use `py` instead of `python` if `python` isn't on your PATH. Stop it with Ctrl+C in the terminal.

## Platform notes

- **Windows:** works out of the box.
- **macOS:** give your terminal Accessibility and Input Monitoring permission (System Settings → Privacy & Security), or it won't hear keys.
- **Linux:** works under X11. Under Wayland, global key listening is blocked, so it may only hear keys typed into its own terminal.

## Tweaking

Lower `MASTER` near the top of the file if it's too loud. Each weapon is its own small function (`shotgun`, `pistol`, `sniper`, ...), so you can reshape one sound without touching the others.
