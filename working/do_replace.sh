#!/bin/bash

#Takes a file whose name ends with '-orig.txt' and adds periods where the last character of the line doesn't have one (for prologues, chapter, pov etc.) Makes sure Edge Browser puts a pause in when reading
#Also does a series of word substitutions from subs.psv to make phoenetic versions of words.

orig_filename="$1"
phon_filename=${orig_filename//-orig.txt/-phon.txt/}
#Add Periods
sed -r 's/^[[:space:]]*(Chapter [[:digit:]]+.*)[[:space:]]+$/\1./' "$orig_filename" >"$phon_filename"
sed -r 's/^[[:space:]]*(Chapter [[:digit:]]+.*)^\.$/\1./' "$orig_filename" >"$phon_filename"
sed -r 's/^[[:space:]]*(Point of view: .*)$/\1./' "$orig_filename" >"$phon_filename"

#Do Word replacements
for word_pair in $(cat subs.psv);do
    old_word=$(echo "$word_pair" | cut -d"|" -f1) 
    new_word=$(echo "$word_pair" | cut -d"|" -f2) 
    sed "s/\b$old_word\b/$new_word/g" "$orig_filename" >"$phon_filename"
done
