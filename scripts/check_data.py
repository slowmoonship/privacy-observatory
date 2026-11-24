#!/usr/bin/env python3
"""Fail closed if any persisted source group cannot support the page."""
import json
from update_data import OUT, GROUPS, validate
for name in GROUPS:
    path = OUT / (name + '.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    validate(name, data['metrics'])
    print(name, 'valid')
