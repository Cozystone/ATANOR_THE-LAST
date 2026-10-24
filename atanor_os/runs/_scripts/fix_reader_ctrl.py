import pathlib
p = pathlib.Path('atanor_os/agent/reader.py')
s = p.read_text(encoding='utf-8')
BS = chr(92)  # backslash
s = s.replace(chr(8), BS + 'b')                                  # backspace characters -> the regex word boundary
s = s.replace("re.split(r'(?<=[.!?])" + BS + "s+|" + chr(10) + "', text)", "re.split(r'(?<=[.!?])" + BS + "s+|" + BS + "n', text)")
p.write_text(s, encoding='utf-8')
bad = [i + 1 for i, l in enumerate(s.split(chr(10))) if any(ord(c) < 32 and c != chr(9) for c in l)]
print('lines with control characters left:', bad)
