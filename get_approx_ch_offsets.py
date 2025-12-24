#!/usr/bin/env python3

#Given an input audiobook file, finds approximate offsets of chapter starts
#Output is array with each index representing a chapter #. We're assuming a chapter zero might take place so
#index 0 is chapter 0 (maybe prologue) etc.
#value at index is -1 if no match found

#Outputs several files with the same basename as input audio file but with different endings.
# <infile>-raw.json = json of data as captured by transcriber
# <infile>.json = processed json file which should include proper chapter numbers etc. This file may need some tinkering before feeding to get_exact_ch_offsets.py
# The output json only has approximate word starts. By having it reprocesses the last 500 frames with the next batch the timing gets slightly off and I never figured out how to make it match perfectly.
# Hopefully some day you'll fix this and feel dumb it was ever wrong.

import sys
import subprocess
import json
import os

from vosk import Model, KaldiRecognizer, SetLogLevel

SAMPLE_RATE = 16000
WORDS_PER_LINE = 7
LOG_ALL = False

FQ_IN_AUDIO_FILE_PATH = sys.argv[1]
WORKING_DIR = os.path.dirname(os.path.abspath(FQ_IN_AUDIO_FILE_PATH))
IN_AUDIO_FILE_PATH = os.path.basename(FQ_IN_AUDIO_FILE_PATH)
IN_AUDIO_FILE_PATH_PARTS = IN_AUDIO_FILE_PATH.split('.')
IN_AUDIO_FILE_PATH_PARTS.pop()
RAW_RESULTS_JSON_FILE_PATH = os.path.join(WORKING_DIR, '.'.join(IN_AUDIO_FILE_PATH_PARTS) + '-raw.json')
CHS_JSON_FILE_PATH = os.path.join(WORKING_DIR, '.'.join(IN_AUDIO_FILE_PATH_PARTS) + '.json')

SetLogLevel(-1)

model = Model(lang="en-us")
rec = KaldiRecognizer(model, SAMPLE_RATE)
rec.SetWords(True)

def text_num_to_num(text: str) -> int:
    """
    Take a string of text that should start with a number spelled out. May also contain extra words which should be ignored.
    Frankly this is a fairly naive implementation just trying to get it mostly there without loading a bunch of dependencies.
    There is already an expectation that the json file that is output will need some manual review, so as long as this is usually
    correct that's good enough.
    """
    ones_pos_mappings = {
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3,
        'four': 4,
        'five': 5,
        'six': 6,
        'seven': 7,
        'eight': 8,
        'nine': 9,
        'ten': 10,
        'eleven': 11,
        'twelve': 12,
        'thirteen': 13,
        'fourteen': 14,
        'fifteen': 15,
        'sixteen': 16,
        'seventeen': 17,
        'eighteen': 18,
        'nineteen': 19,
    }
    other_num_words_mappings = {
        'twenty': 20,
        'thirty': 30,
        'forty': 40,
        'fifty': 50,
        'sixty': 60,
        'seventy': 70,
        'eighty': 80,
        'ninety': 90
    }
    num_as_words = text.split(' ')
    running_total = -1
    last_type = ''
    for i in range(len(num_as_words) - 1):
        current_word = num_as_words[i]
        next_word = num_as_words[i + 1]
        current_num = 0
        if i > 0 and current_word == 'chapter': #If this word encountered likely the text that follows refers to the following chapter, so exit
            break
        if current_word in ones_pos_mappings.keys() or current_word in other_num_words_mappings.keys():
            if running_total == -1:
                running_total = 0
            #Don't allow two of the ONES_POS words in a row. These should be at the end or else followed up by something like hundred, thousand, etc.
            if current_word in ones_pos_mappings.keys() and last_type != 'ONES_POS':
                current_num = ones_pos_mappings[current_word]
                last_type = 'ONES_POS'
            elif current_word in other_num_words_mappings.keys():
                current_num = other_num_words_mappings[current_word]
                last_type = 'OTHER_POS'
            if next_word == 'hundred':
                current_num *= 100
            elif next_word == 'thousand':
                current_num *= 1000
        running_total += current_num
    last_entry = num_as_words[-1]
    if last_entry in ones_pos_mappings.keys() or last_entry in other_num_words_mappings.keys():
        if last_entry in ones_pos_mappings.keys() and last_type != 'ONES_POS':
            current_num = ones_pos_mappings[last_entry]
        elif last_entry in other_num_words_mappings.keys():
            current_num = other_num_words_mappings[last_entry]
        running_total += current_num
    return running_total

def transcribe():
    results = []
    command = ["ffmpeg", "-nostdin", "-loglevel", "quiet", "-i", FQ_IN_AUDIO_FILE_PATH,
               "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        capture_cnt = -1
        data = []
        offset = 0
        one_accepted = False
        loop_count = 0
        while True:
            loop_count += 1
            if loop_count % 2500 == 0:
                print ('Saving interim data')
                with open(RAW_RESULTS_JSON_FILE_PATH, 'w') as json_file:
                    json.dump(results, json_file)
            if len(data) == 0:
                new_data = process.stdout.read(4000)
                data = new_data[:]
            else:
                new_data = process.stdout.read(3500)
                data = data[-500:] + new_data
                if one_accepted: #For some reason this totally messes up if one AcceptWaveform isn't yet accepted before starting to count the offset.
                    #We're re-including the last 500 bytes of data in case the word 'chapter' crosses that boundary (it happened on one test case)
                    #For whatever reason this causes it to only get close. It's not quite perfect. Math error? Idk. It's close
                    offset += 500
            if len(new_data) == 0:
                break
            if rec.AcceptWaveform(data):
                one_accepted = True
                res = json.loads(rec.Result())
                if res['text'] != '':
                    for entry in res['result']:
                        entry['start'] -= (offset / (SAMPLE_RATE * 2)) #Data is mono but I have to double the sample rate?? Why?
                        entry['end'] -= (offset / (SAMPLE_RATE * 2))
                        if entry['word'] == 'chapter':
                            capture_cnt = 0
                        if capture_cnt >= 0 or LOG_ALL:
                            results.append(entry)
                            capture_cnt +=1
                        if capture_cnt == 9:
                            capture_cnt = -1
    res = json.loads(rec.FinalResult())
    print ('Finalized Result:')
    print (res)
    with open(RAW_RESULTS_JSON_FILE_PATH, 'w') as json_file:
        json.dump(results, json_file)
    return results


if __name__ == "__main__":
    all_ch_words = transcribe()
    #with open(RAW_RESULTS_JSON_FILE_PATH, 'r') as json_file:
    #    all_ch_words = json.load(json_file)

    indexes = []
    ch_words = []
    ch_start = 0
    for i in range (len(all_ch_words)):
        if all_ch_words[i]['word'] == 'chapter' or i == len(all_ch_words) - 1:
            start_index = i + 1
            end_index = start_index + 9
            ch_start = all_ch_words[i]['start']
            if end_index >len(all_ch_words) -1:
                end_index = len(all_ch_words) - 1
            ch_words = [i['word'] for i in all_ch_words[start_index:end_index] ]
            if len(ch_words) > 0:
                ch_num = text_num_to_num(' '.join(ch_words))
                if ch_num > -1:
                    indexes.append({
                        'index': len(indexes),
                        'start': ch_start,
                        'chapter': ch_num,
                        'ch_words': ch_words,
                    })
                ch_words = []
    with open(CHS_JSON_FILE_PATH, 'w') as json_file:
        json.dump(indexes, json_file)
    print(json.dumps(indexes))