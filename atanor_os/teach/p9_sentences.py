"""P9 training sentences (teacher = Claude, training only; never imported by agent/ or the evaluation process).

Labels: tool, ext ('any' = all files) and destination. Training extensions: txt, csv, md.
The teacher also wrote the sealing instructions for the evaluation author; to keep the test conservative these
training sentences avoid the example verbs given there (duplicate, back up, relocate, shift, put, stash, remove,
erase, get rid of, trash) and its example type phrases ('ending in', 'spreadsheets', 'logs').
"""
import random

COPY = ['Copy {sel} into a new folder called {d}.', 'Make a copy of {sel} in a folder named {d}.', 'Please copy {sel} to {d}.',
        'Clone {sel} into the {d} folder.', 'Copy {sel} over to a fresh folder {d}, keeping the originals.',
        'I want a copy of {sel} inside a new folder named {d}.', 'Replicate {sel} into {d}.']
MOVE = ['Move {sel} into a new folder called {d}.', 'Transfer {sel} to a folder named {d}.', 'Please move {sel} to {d}.',
        'Carry {sel} over into the {d} folder.', 'Move {sel} into {d} and leave nothing behind.',
        'Place {sel} in a new folder named {d}, not keeping the originals.', 'Could you move {sel} into a folder called {d}?']
DELETE = ['Delete {sel}.', 'Please delete {sel}.', 'Discard {sel}.', 'Wipe out {sel}.', 'Throw away {sel}.',
          'Delete {sel} from the workspace.', 'I no longer need {sel}; delete them.']
SEL = {'txt': ['the txt files', 'all text files', 'every .txt file', 'the text files'],
       'csv': ['the csv files', 'all csv files', 'every .csv file', 'the comma separated files'],
       'md': ['the markdown files', 'all md files', 'every .md file', 'the markdown documents'],
       'any': ['all files', 'every file', 'all of the files', 'each file']}
DESTS = ['harvest', 'lantern', 'meadow', 'orchard', 'pebble', 'quiver', 'ribbon', 'saddle', 'thimble', 'valley', 'walnut',
         'anchor', 'beacon', 'canyon', 'dagger', 'falcon', 'garnet', 'hollow', 'island', 'jasmine', 'kettle', 'locket',
         'marble', 'nugget', 'oyster', 'parcel', 'quarry', 'raven', 'summit', 'tunnel', 'velvet', 'wicket', 'yonder',
         'acorn', 'bramble', 'candle', 'dewdrop', 'emblem', 'feather', 'goblet', 'hammock', 'icicle', 'juggler', 'kernel',
         'ladder', 'mantle', 'napkin', 'oracle', 'pillow', 'quilt', 'rocket', 'spindle', 'teapot', 'umpire', 'vessel', 'whistle']


def sentences():
    rng = random.Random('p9-teacher-v1')
    out, d_i = [], 0
    for tool, templates in (('copy', COPY), ('move', MOVE), ('delete', DELETE)):
        for k in range(28):
            ext = ('txt', 'csv', 'md', 'any')[k % 4]
            sel = SEL[ext][(k // 4) % 4]
            dest = None
            if tool != 'delete':
                dest = DESTS[d_i]
                d_i += 1
            s = templates[k % len(templates)].format(sel=sel, d=dest)
            out.append({'id': f'train-{tool}-{k:02d}', 'sentence': s, 'tool': tool, 'ext': ext, 'dest': dest})
    rng.shuffle(out)
    return out
