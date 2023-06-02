# inasavesalot

...name is still work in progress.

Basically, Ina saves quite a lot and it was most notable during her Breath of the Wild playthough. So naturally, given the EU timezone, I was watching Ina at 5 AM and the sudden motivation to do another project struck me.

A year ago? Two years ago? Dunno, time flies by quick, I made [`inadoki`](https://github.com/vignedev/inadoki), which monitored Ina's heart rate monitor during her Horror Week. That project was written in the same way like this one, at 5 AM with a ton of caffeine coursing through my blood veins. However, this project will differ a bit from the other one, most notably by using Python instead of Bash-ing my way through it.

## Usage

This project is specifically tailored to detect the BoTW saving dialog and it is quite simple. To use this, you basically run:

```console
$ python3 __main__.py -h
usage: __main__.py [-h] -g GEOMETRY -i INPUT [-ss START] [-n THREADS] [output]

positional arguments:
  output                Path to output detected timestamps. Defaults to stdout.

options:
  -h, --help            show this help message and exit
  -g GEOMETRY, --geometry GEOMETRY
                        Geometry in pixels where the dialog should appear (WxH+X+Y)
  -i INPUT, --input INPUT
                        Input video file or a still frame
  -ss START, --start START
                        Start from this frame
  -n THREADS, --threads THREADS
                        How many CPU threads to use. (Defaults to all)
```

For example:
```console
$ python3 __main__.py -g 247x36+515+412 -i o7BSE-74u8U_720.webm o7BSE-74u8U.csv -n 4
```

## Source collection

The data I collected used 720p30, given that the part I am monitoring should be fairly distinguishable even under lower bitrate and resolution. To do this, I used `yt-dlp` with as following:

```console
$ yt-dlp -S '+size' -f 'bestvideo[height=720]' -o '%(id)s.%(ext)s' <video_url>
```

After that, just plug it into the program itself and carry on.

## License

MIT