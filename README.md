# reMy, a reMarkable tablet manager app

The goal of reMy is to allow simple interaction with the reMarkable tablet over ssh, without needing the cloud service, nor the USB Web UI.


**BEWARE**

This is a work-in-progress with incomplete features.
It has not been thoroughly tested.
These instructions are preliminary and will be expanded with time.
Feel free to populate the wiki!

I did my best to make sure usage of reMy will not incur in data loss.
Most of the features exclusively read from the tablet and are completely safe, even if they may fail on the computer side.
The only features that alters data on the tablet is the upload feature.
It is however very unlikely to cause any problem since it only adds files.
In any case, it is highly advisable to back up your data before playing with it!

For a basic backup of the tablet's data:

    scp -rp REMARKABLEHOST:/home/root/.local/share/remarkable/xochitl .


## Installation

The installation process is a bit less straightforward than ideal because `python-poppler-qt5` has [broken installation scripts](https://github.com/frescobaldi/python-poppler-qt5/pull/41).

The requirements are:

- requests
- sip
- arrow
- paramiko
- PyPDF2
- PyQt5
- simplification (this requires python < 3.9, but I plan to make this dependency optional)
- python-poppler-qt5 (see below)

The following works on MacOs (Catalina), assuming `python` version 3.8 (if not, use `pyenv` to install and manage Python versions):

```bash
# Build dependencies
brew install cmake poppler
# Install regular dependencies
pip install requests arrow paramiko PyPDF2 PyQt5 simplification sip
# Install python-poppler-qt5 using SIP5
pip install git+https://github.com/mitya57/python-poppler-qt5.git@sip5
```


## Usage

The main intended usage is as a GUI for connecting to the tablet.
The app however also supports reading from a local backup.
The main entry point for the app is `remygui.py`.

## Configuration

Starting it the fist time with `python remygui.py` will print an error message with the path where the app is expecting to find a configuration file (on macOS it would be something like `/Users/<user>/Library/Preferences/remy.json`).
Create a JSON file at that path with the following structure:

```json
{
  "sources": {
      "source1": {...},
      "source2": {...},
      ...
  },
  "default_source": "source1",
  "preview": {...},
  "export": {...},
  "mathpix" : {...}
}
```

The only mandatory section is `sources`.
Each section is documented below.
The file `example_config.json` is an example configuration that you can adapt to your needs.
**IMPORTANT**: the format is vanilla JSON; trailing commas and C-like comments are **not supported**. The file is parsed using Python's standard `json` module.

### Source types
Each source defines a possible way to get the contents to display.
The `default_source` settings indicates which source to load if none is specified in the command line.
If `default_source` is `false` or not set, then reMy shows a dialog allowing you to pick a source among the available ones.
There are three supported kinds of sources: `local`, `ssh` and `rsync`.

#### Local source

A `local` source expects to find the data at a local path (e.g. from a backup folder):
```json
{
  "name": "Latest Backup",
  "type": "local",
  "documents": "/path-to/backup/latest",
  "templates": "/path-to/templates"
}
```
The `documents` folder is expected to have the same structure as the `/home/root/.local/share/remarkable/xochitl` on the tablet.
The "maintenance" folders `.cache`, `.thumbnails`, `.textconversion`, `.highlights` are not needed.
The `templates` folder is expected to be a local copy of the `/usr/share/remarkable/templates` folder on the tablet.
Obviously, this source is read-only: you cannot upload PDFs to it.

#### SSH source

```json
{
  "name": "reMarkable (WiFi)",
  "type": "ssh",
  "address": "192.168.1.154",
  "key": "~/.ssh/id_rsa_remarkable",
  "username": "root",
  "timeout": 3,
  "use_banner": "remy-banner.png",
}
```

The SSH-type source connects to the tabled via SSH.
The tablet needs to be either plugged via USB
(in which case you should set `"address": "10.11.99.1"`)
or via WiFi, in which case you need to find the address assigned to the tablet in the "About" section of the tablet's settings.
Most settings are optional, you can also use `password` instead of `key`.
Address is mandatory.
The `use_banner` setting is optional and described below.


#### Rsync source

```json
{
  "name": "reMarkable (RSync)",
  "type": "rsync",
  "data_dir": "/path-to/remy",
  "address": "10.11.99.1",
  "host": "rm",
  "key": "~/.ssh/id_rsa_remarkable",
  "username": "root",
  "timeout": 3,
  "use_banner": "remy-banner.png"
}
```

This is an optimised version of the SSH source.
While SSH works without extra dependencies, the rsync source requires `rsync` to be installed on the reMarkable.
Most settings are the same, you can also set `host` to your SSH-config alias for the remarkable.
A mandatory setting is `data_dir` which should point to a directory which can be managed by reMy to keep a partial copy of the tablet's data.
Every time you connect, only the changes are downloaded.
The data-heavy files (PDFs and .rm) are downloaded on demand.


#### The `use_banner` option

When this option is set, the main UI of the tabled will be temporarily disabled while reMy is open.
This is intended as an helpful prompt and a way to avoid conflicts on data access.
The feature works best if the setting is the filename (can be absolute, or relative to home) of a png file stored on the tablet (there's a nice `remy-banner.png` in the asset folders you can upload with `scp`) and [`remarkable-splash`](https://github.com/ddvk/remarkable-splash) is installed on the tablet.

If reMy crashes and the remarkable seems unresponsive it is only because reMy re-enables the main UI of the tabled on exit; to regain control of the tablet you have three options: try and run reMy again and close it cleanly; or run `ssh REMARKABLEHOST /bin/systemctl start xochitl`; or manually reboot the device. Don't worry nothing bad is happening to the tablet in this circumstance.

### Preview options

The `preview` section for now has one option only: `eraser_mode`.
It can take two values: `"accurate"` or `"quick"` (default is `"quick"`).
The quick method paints white strokes to render the eraser tool.
This results in quicker rendering times but inaccurate results: the layers below the strokes would be covered by the eraser which is undesirable.
The export function always uses the accurate method: clipping the paths to exclude erased areas. Accurate mode is slower to render due to the clipping, so it is optional in preview mode.

```json
"preview": {
  "eraser_mode": "quick"
}
```
### Export options

The export section has two settings:

```json
"export": {
  "default_dir": "...",
  "open_exported": true
}
```

### Mathpix options

To use the mathpix API you need to obtain personal tokens at https://mathpix.com/ocr (they have a free plan).
Once obtained, the API tokens should be saved in the configuration as follows:

```json
"mathpix" : {
  "app_id":"xxx_xxx_xxx_xxx_xxxxxx",
  "app_key":"xxxxxxxxxxxxxxxxxxxx"
}
```

The support for mathpix is currently experimental.
Only one page at a time can be exported (via context menu in preview) and the data is sent in vector form, which means the eraser tool is ignored.


## Features

Once the configuration file contains the necessary info, you can run reMy by running

    python remygui.py [SOURCE]

The option is the id of one of the sources defined in the configuration file.
With no option, the default source will be selected.

The app displays the tree of the files in the main window.

### Preview

Double clicking on a PDF or notebook will open a preview window.
Use the arrows to got to next/prev page. You can zoom in and out with + and - or mouse wheel. Ctrl+Left/Right rotates the view. The context menu shows some further actions.
Pressing S increases the simplification of the lines, Shift+S decreases it (this is only a rendering effect, the notebooks are unaffected). This is just a preview of an experimental feature.


### Export and rendering

PDFs are rendered at a fixed resolution for quick preview.
The export function overlays the vectorial data from annotations to the original PDF so the quality of both is preserved.

The rendering of notebooks/annotations has been redeveloped from scratch.
It features proper handling of eraser/eraser area: other renderers just produce a white fill/stroke but that does not work well with layers nor with annotations on PDFs; for the moment this faster way of dealing with it is used for eraser in preview mode, but the accurate one is used for the export function.
For the moment the export function simplifies the lines a bit, to achieve smaller sizes.
This will become a fully customizable parameter once the tool matures.

Planned features include: fully parametric rendering to be able to control the colors/style of each element from settings.

### Upload

From the tree view, select a folder (or deselect to select the root) and drag and drop on the info panel any PDF (mutiple PDFs at once are supported, folders are planned but not supported yet).
For the moment, the UI blocks until upload is completed.
Progress bars coming soon ;)



- - -

Every source can in addition overwrite other global settings
by using the `settings` key, for example you could have a per-source default export folder:

```json
{
  "sources": {
    "source1": {...},
    "source2": {
      ...
      "settings": {
        "export": {
          "default_dir": "/path-to/love-letters"
        }
      }
     },
    ...
  },
  "export": {
    "default_dir": "/path-to/work"
  }
}
```


## Disclaimer

This project is not affiliated to, nor endorsed by, [reMarkable AS](https://remarkable.com/).
**I assume no responsibility for any damage done to your device due to the use of this software.**

## Licence

GPLv3