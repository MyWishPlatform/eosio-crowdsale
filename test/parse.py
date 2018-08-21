import re

with open('src/config.h', 'r') as h_file\
        , open('test/config.ini', 'w') as ini_file:
    print('[DEFAULT]', file=ini_file)
    for line in h_file.readlines():
        match = re.search('#define (\w+) (\w+)', line)
        if match:
            print(match.group(1), match.group(2), sep=' = ', file=ini_file)
