"""SEALED surface forms for probes (evaluator side only). None of these verbs, selector phrases or destination frames
appears in any generated life or in the teacher's answers; they exist only to test whether what a mind learned from
the TRAIN forms transfers to expressions it has never met. Do not use them for development."""

FS_SEALED = {
    'verbs': {'move': [['migrate'], ['send']], 'copy': [['mirror'], ['reproduce']], 'delete': [['purge'], ['wipe', 'out']]},
    'select': {'csv': [['tabular', 'files']], 'log': [['log', 'records']], 'txt': [['plain', 'text', 'files']],
               'json': [['json', 'data']], 'md': [['markdown', 'pages']]},
    'dest': [['over', 'to', 'a', 'folder', 'titled', '{d}'], ['under', 'a', 'directory', 'labelled', '{d}']],
}
