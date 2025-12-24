import sys
import os
import math
import csv
import subprocess

def get_media_end(audio_file_path: str):
    command = f"/usr/bin/ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{audio_file_path}'"
    result = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
    return float(result.stdout.strip('\n'))


title = sys.argv[1]
artist = sys.argv[2]
album = sys.argv[3]
FQ_AUDIO_FILE_PATH = os.path.abspath(sys.argv[4])
media_end = get_media_end(FQ_AUDIO_FILE_PATH)
WORKING_DIR = os.path.dirname(FQ_AUDIO_FILE_PATH)
AUDIO_FILE_PATH = os.path.basename(FQ_AUDIO_FILE_PATH)
AUDIO_FILE_PATH_PARTS = AUDIO_FILE_PATH.split('.')
AUDIO_FILE_PATH_PARTS.pop()
#Assume the psv file are the same as audio file but w/ diff extension
OFFSETS_PSV_FILE_PATH = os.path.join(WORKING_DIR, '.'.join(AUDIO_FILE_PATH_PARTS) + '.psv')
TOML_OUT_PATH = os.path.join(WORKING_DIR, '.'.join(AUDIO_FILE_PATH_PARTS) + '.toml')
JPG_FILE_PATH = os.path.join(WORKING_DIR, '.'.join(AUDIO_FILE_PATH_PARTS) + '.jpg')
M4B_FILE_PATH = os.path.join(WORKING_DIR, '.'.join(AUDIO_FILE_PATH_PARTS) + '.m4b')

offsets = []
with open(OFFSETS_PSV_FILE_PATH, 'r') as csv_file:
    reader = csv.DictReader(csv_file, delimiter='|')
    for row in reader:
        offsets.append(row)

out_contents = f""";FFMETADATA1
TITLE={title}
ARTIST={artist}
ALBUM={album}
GENRE=Audiobook
"""
start = 0
for i in range(0, len(offsets)):
    offset = offsets[i]
    if i < len(offsets) - 1:
        next_offset = offsets[i + 1]
        end = math.trunc(float(next_offset['offset']) * 1000)
    else:
        end = math.trunc(float(media_end) * 1000)
    title = offset['title']
    out_contents += f"""
[CHAPTER]
TIMEBASE=1/1000
START={start}
END={end}
TITLE={title}
"""
    start = end

with open(TOML_OUT_PATH, 'w') as outfile:
    outfile.write(out_contents)

print ('metadata file create. You can combine wit hthe following:')
print (f'ffmpeg -i "{FQ_AUDIO_FILE_PATH}" -i "{JPG_FILE_PATH}" -i "{TOML_OUT_PATH}" -map 0:0 -map 1:0 -map_metadata 2 -c:v copy -c:a aac -ac 1 -disposition:v attached_pic "{M4B_FILE_PATH}"')

#Metadata info
#This file will contain global metadata (like title, artist) and chapter information. The format is specific to FFmpeg's ffmetadata format.
#Code
#
#;FFMETADATA1
#title=My Audiobook Title
#artist=Author Name
#album=Album Name
#genre=Audiobook
#
#[CHAPTER]
#TIMEBASE=1/1000
#START=0
#END=120000
#title=Introduction
#
#[CHAPTER]
#TIMEBASE=1/1000
#START=120000
#END=360000
#title=Chapter 1
#
#[CHAPTER]
#TIMEBASE=1/1000
#START=360000
#END=600000
#title=Chapter 2
#
#    TIMEBASE: Defines the unit for START and END (e.g., 1/1000 for milliseconds).
#    START and END: Specify the chapter's start and end times in the defined TIMEBASE.
#    title: The chapter's title.
#
#. Combine audio and metadata using FFmpeg:
#ffmpeg -i /home/jason/Videos/Inferno.flac -i Inferno.png -i metadata.toml -map 0:0 -map 1:0 -map_metadata 2 -c:v copy -c:a aac -ac 1 -disposition:v attached_pic '04. Inferno.m4b'