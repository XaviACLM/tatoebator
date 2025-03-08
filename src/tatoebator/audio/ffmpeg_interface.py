import subprocess
import sys

if sys.platform == "win32":
    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _startupinfo.wShowWindow = subprocess.SW_HIDE
else:
    _startupinfo = None


def convert_bitrate(input_file, output_file, target_bitrate, overwrite=False):
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error',
         '-y' if overwrite else ''
                                '-i', input_file,
         '-b:a', target_bitrate,
         output_file],
        shell=False, startupinfo=_startupinfo,
        stdout=subprocess.DEVNULL)
