# ttml2srt
convert TTML subtitles to SRT subtitles

## Usage

```
python3 ttml2srt.py --help
```


```
usage: ttml2srt.py [-h] [-i INPUT] [-o OUTPUT] [--std-out] [-g GLOB]
                   [-f FORMAT]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        The ttml file to parse
  -o OUTPUT, --output OUTPUT
                        The file to store the output in
  --std-out             Print output to std-out
  -g GLOB, --glob GLOB  Used to parse multiple files using a globpatter - you
                        should also specify --format
  -f FORMAT, --format FORMAT
                        Format to save files as - used with --glob (Default:
                        {filename}.srt)
```

## Convert a single TTML to SRT:
```
python3 ttml2srt.py --input "mysubtitle.ttml" --output "mysubtitle.srt"
```

## Convert based on glob pattern
```
python3 ttml2srt.py --glob "*.ttml" --format "{filename}.srt"
```
Note that the glob pattern and format string should be escaped depending on which shell you are using. This is especially important with regards to glob patterns and the `{}` in `--format`.

The available variables in `--format` are
```
filename: the base filename, without extension and without the path
ext: file extension
dir: absolute path of the directory of the file
file: filename + extension
```