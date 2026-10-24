"""Limited Korean instructions -> structured goals for the view body (charter §6, 언어).

This is PROVIDED grammar, not learned language. Supported forms are listed in SUPPORTED; anything
else is reported in `unsupported` instead of being guessed. '이것/저것/이 패널' resolve to the current
selection; without one the parser asks instead of assuming.
"""
import re

from ..core.types import Goal, Literal
from ..eval.generator import BUDGET

EXT_WORDS = {'txt': 'txt', '텍스트': 'txt', 'csv': 'csv', 'md': 'md', '마크다운': 'md', 'log': 'log', '로그': 'log',
             'json': 'json', '전부': 'all', '모두': 'all', '전체': 'all'}
KEY_WORDS = {'이름': 'name', '확장자': 'ext', '크기': 'size'}
PANEL_WORDS = {'첫째': 'p1', '첫': 'p1', '둘째': 'p2', '셋째': 'p3', '비교': 'cmp'}
SUPPORTED = [
    '<패널>(을/를) 열어',
    '<패널>(을/를) 닫아',
    '<패널>(에/에서) <확장자>만 보여줘 / <확장자>만 보이게',
    '<패널>(을/를) <이름|확장자|크기>순으로 정렬',
    '<패널>(을/를) 확장자별로 묶어 / 묶지 마',
    '<패널>(을/를) <패널>(와/과) 비교',
    '이것/저것/이 패널 = 현재 선택',
    '절은 쉼표, "그리고", "그 다음"으로 잇는다',
]
DEIXIS = ('이것', '저것', '이 패널', '그것')


def _panel(tok, selection):
    tok = tok.strip()
    if tok in DEIXIS:
        return selection
    m = re.fullmatch(r'(p[123]|cmp)', tok)
    if m:
        return m.group(1)
    return PANEL_WORDS.get(tok)


def parse(text, selection=None, state=None):
    """Returns {'goal': Goal|None, 'literals': [...], 'unsupported': [...], 'ask': str|None}."""
    clauses = [c.strip() for c in re.split(r',|그리고|그 다음|그다음', text) if c.strip()]
    lits, unsupported, ask = [], [], None
    for c in clauses:
        m = re.fullmatch(r'(.+?)\s*(?:을|를)?\s*열어(?:줘)?', c)
        if m and _panel(m.group(1), selection):
            lits.append(Literal('kind', (_panel(m.group(1), selection),), 'panel'))
            continue
        m = re.fullmatch(r'(.+?)\s*(?:을|를)?\s*닫아(?:줘)?', c)
        if m and _panel(m.group(1), selection):
            lits.append(Literal('kind', (_panel(m.group(1), selection),), 'absent'))
            continue
        m = re.fullmatch(r'(.+?)\s*(?:에서|에)?\s*(\S+?)\s*만\s*(?:보여줘|보이게(?: 해)?)', c)
        if m and _panel(m.group(1), selection) and m.group(2) in EXT_WORDS:
            p = _panel(m.group(1), selection)
            lits += [Literal('kind', (p,), 'panel'), Literal('filter', (p,), EXT_WORDS[m.group(2)])]
            continue
        m = re.fullmatch(r'(.+?)\s*(?:을|를)?\s*(이름|확장자|크기)\s*순(?:으로)?\s*정렬(?:해)?', c)
        if m and _panel(m.group(1), selection):
            p = _panel(m.group(1), selection)
            lits += [Literal('kind', (p,), 'panel'), Literal('sort', (p,), KEY_WORDS[m.group(2)])]
            continue
        m = re.fullmatch(r'(.+?)\s*(?:을|를)?\s*확장자별로\s*묶어(?:줘)?', c)
        if m and _panel(m.group(1), selection):
            p = _panel(m.group(1), selection)
            lits += [Literal('kind', (p,), 'panel'), Literal('group', (p,), 'ext'), Literal('filter', (p,), 'all')]
            continue
        m = re.fullmatch(r'(.+?)\s*(?:을|를)?\s*묶지\s*마', c)
        if m and _panel(m.group(1), selection):
            lits.append(Literal('group', (_panel(m.group(1), selection),), 'none'))
            continue
        m = re.fullmatch(r'(\S+?)(?:을|를)?\s+(\S+?)(?:와|과)\s*비교(?:해)?(?:줘)?', c)
        if m and _panel(m.group(1), selection) and _panel(m.group(2), selection):
            c_, p = _panel(m.group(1), selection), _panel(m.group(2), selection)
            lits += [Literal('kind', (c_,), 'compare'), Literal('kind', (p,), 'panel')]
            continue
        if any(d in c for d in DEIXIS) and selection is None:
            ask = f'"{c}"에서 가리키는 패널이 무엇인지 알 수 없습니다. 어느 패널인가요?'
            continue
        unsupported.append(c)
    goal = None
    if lits and not unsupported and ask is None:
        keep = []
        if state:                                             # panels the instruction does not mention stay as they are
            mentioned = {l.args[0] for l in lits}
            keep = [Literal('kind', (p,), o['kind']) for p, o in state.items()
                    if ':' not in p and p not in mentioned and o['kind'] in ('panel', 'compare')]
        goal = Goal('instruction', lits, keep, {'close_panels': any(l.value == 'absent' for l in lits)}, dict(BUDGET), [])
    return {'goal': goal, 'literals': lits, 'unsupported': unsupported, 'ask': ask}
