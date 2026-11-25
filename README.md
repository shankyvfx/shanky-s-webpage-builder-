# Shanky’s Website Builder

A local visual editor for static HTML websites. Create a website or import your own folder/ZIP, edit its pages and popups, and save or export the result.

## Start

Requires Python 3.10 or newer. On Windows, double-click `Start-Shankys-Builder.bat`, or run:

```sh
python studio.py
```

Open http://127.0.0.1:8937/. Preview uses port 8938. Set `STUDIO_PORT` to change both ports. The server binds to your computer’s loopback interface.

## Editing

- Design: add text/photos and align multiple selections.
- Properties: edit the selected object; lock/unlock, copy/paste, resize, rotate, colors and links.
- Elements: collapsible button, icon, shape and photo-frame libraries.
- Animate: text and element animation presets.
- Shift/Ctrl-click adds or removes objects from selection. Selected items can move together.
- Pages includes editable popups. Undo/Redo restores canvas changes.
- Save writes a working copy and updates the chosen original folder, with backups and outside-edit checks. New projects and ZIP imports ask for a destination folder.
- Cleanup reviews old unused image uploads and moves selected files to restorable project Trash.

## Source layout

```text
app/                 Browser interface and builder icon
studio.py            Local server and website operations
source_save.py       Backed-up, conflict-checked folder saving
site_structure.py    Organized website files and asset paths
file_cleanup.py      Conservative review, Trash and restore
reference_tools.py   Public-reference inspection
ai_providers.py      Optional generic provider adapters
```

Reference recreation supports a manual ChatGPT browser handoff without API requests. Optional provider code requires the user’s own explicit setup and generation consent; no account connection or credentials are supplied.

## Private data

This repository contains only the builder application. No client websites, portfolios, sample sites, personal images, project history, source-folder connections or saved provider credentials are included. Runtime data is created locally under `workspace/` and ignored by Git. Do not commit that folder or protected connection files.

The editor targets static HTML/CSS sites. Arbitrary scripted sites and responsive visual edits still require preview review. Text and image reconstruction from flattened screenshots is approximate.
