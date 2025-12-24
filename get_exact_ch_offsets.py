import sys
import os
import subprocess
import json
from vosk import Model, KaldiRecognizer

#Takes an input audio file as command-line argument
#Expects a file with the same name but .txt extension which includes the original text (To get chapter names)
#Also expects a .json file with the same name to be present in same directory which is output from get_approx_ch_offsets.py
#The fact that we even have to take this extra step is a failure on the part of get_approx_ch_offsets.py. See that file for more details.

#Outputs a psv file (and to stdout) a psv of the finalized data

if len(sys.argv) < 2:
    print ('Missing input audio file name')
    sys.exit(1)

SAMPLE_RATE = 16000
IN_AUDIO_FILE_PATH = sys.argv[1]
IN_AUDIO_FILE_PATH_PARTS = IN_AUDIO_FILE_PATH.split('.')
IN_AUDIO_FILE_PATH_PARTS.pop()
#Assume the txt file and offsets file are the same as audio file but w/ diff extensions
ORIG_TXT_FILE_PATH = '.'.join(IN_AUDIO_FILE_PATH_PARTS) + '-orig.txt'
OFFSETS_JSON_FILE_PATH = '.'.join(IN_AUDIO_FILE_PATH_PARTS) + '.json'
OUTPUT_CSV_FILE_PATH = '.'.join(IN_AUDIO_FILE_PATH_PARTS) + '.psv'

if not os.path.exists(OFFSETS_JSON_FILE_PATH):
    print ('Missing offsets json file ' + OFFSETS_JSON_FILE_PATH)
    sys.exit()
if not os.path.exists(ORIG_TXT_FILE_PATH):
    print ('Missing txt file ' + ORIG_TXT_FILE_PATH)
    sys.exit()

def get_real_chapter_name(ch_num: int, txt_file_path) -> str:
    command = f"/usr/bin/grep '^Chapter {ch_num}\\.' '{txt_file_path}'"
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
        return result.stdout.strip('\n ')
    except Exception as e:
        print(e)
    return ''


def make_audio_segment(around_time, in_audio_file_path, out_audio_file_path):
    begin_time = around_time - 15
    end_time = around_time + 15
    command = f"ffmpeg -y -ss {begin_time} -to {end_time} -i '{in_audio_file_path}' -ac 1 '{out_audio_file_path}'"

    try:
        subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"Error output: {e.stderr}")
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def get_ch_offset(rec: KaldiRecognizer, approx_offset: float, word_to_search: str = 'chapter'):
    begin_time = approx_offset - 15
    end_time = approx_offset + 15
    command = ["ffmpeg", "-nostdin", "-loglevel", "quiet", "-ss", str(begin_time), "-to", str(end_time), "-i",
               IN_AUDIO_FILE_PATH, "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"]
    text = []
    ch_text = []
    offset = 0
    total_read = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        while True:
            data = process.stdout.read(4000)
            total_read += len(data)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                results = json.loads(rec.Result())
                results_len = len(results['result'])
                for wi in range(results_len):
                    word_obj = results['result'][wi]
                    if word_obj['word'] == word_to_search:
                        offset = word_obj['start']
                        start_index = wi
                        end_index = wi + 9
                        if end_index > results_len:
                            end_index = results_len
                        words = [i['word'] for i in results['result'][start_index:end_index]]
                        ch_text = ' '.join(words)
                text.append(results['text'])
        return offset, ch_text, (total_read / SAMPLE_RATE / 2)



with open(OFFSETS_JSON_FILE_PATH, 'r') as json_file:
    offsets_obj = json.load(json_file)

#Vosk init
model = Model(lang="en-us")
rec = KaldiRecognizer(model, SAMPLE_RATE)
rec.SetWords(True)
rec.SetPartialWords(True)

total_secs_processed = 0
total_frames_read = 0
ch_num = 0
psv_contents = "ch_num|offset|title|words\n"
for offset_obj in offsets_obj:
    approx_offset = offset_obj['start']
    ch_num += 1
    if approx_offset < 0:
        continue
    word_to_search = 'chapter'
    wav_file_path = "tmp.wav"
    for try_num in range(4):
        approx_offset += try_num
        ch_offset, text, secs_processed = get_ch_offset(rec, approx_offset, word_to_search)
        ch_offset -= total_secs_processed
        if ch_offset > 0:
            if ch_num == 0:
                ch_offset -= 0.025
            else:
                ch_offset += approx_offset - 15 - 0.025
        total_secs_processed += secs_processed
        if ch_offset > 0:
            correct_ch_name = get_real_chapter_name(ch_num, ORIG_TXT_FILE_PATH)
            outstr = str(ch_num) + '|' + str(ch_offset) + '|' + correct_ch_name + '|' + str(text)
            psv_contents += outstr + '\n'
            print (outstr)
            break

print (psv_contents)
print ('You may need to manually fix entries, especially first/last entries.')
with open(OUTPUT_CSV_FILE_PATH, 'w') as psv_file:
    psv_file.write(psv_contents)
