"""Post-process the generated DOCX so all numbers show in Arabic-Indic digits, independent of Word's
"Numeral" option:
- footer page numbers built from nested Word fields ({IF {=MOD(INT({PAGE}/10),10)} = 3 "٣" ""} …);
- footnote marks become custom marks «(١)» (continuous numbering) in the text and in the footnote area.
Usage: python docx_post.py file.docx   (in place)"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

AR = "٠١٢٣٤٥٦٧٨٩"
RPR = ('<w:rPr><w:rFonts w:ascii="Traditional Arabic" w:hAnsi="Traditional Arabic" w:cs="Traditional Arabic"/>'
       '<w:rtl/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>')


class X(str):
    """Raw XML (a nested field) as opposed to instruction text."""


def r_fld(t):
    return f'<w:r>{RPR}<w:fldChar w:fldCharType="{t}"/></w:r>'


def r_instr(s):
    return f'<w:r>{RPR}<w:instrText xml:space="preserve">{s}</w:instrText></w:r>'


def r_text(s):
    return f'<w:r>{RPR}<w:t xml:space="preserve">{s}</w:t></w:r>'


def field(*parts, result=""):
    body = "".join(p if isinstance(p, X) else r_instr(p) for p in parts)
    return X(r_fld("begin") + body + r_fld("separate") + r_text(result) + r_fld("end"))


def page():
    return field(" PAGE ", result="1")


def digit_of(div):
    return field(" = MOD(INT(", page(), f" / {div}), 10) ", result="1")


def digit_chars(div):
    return X("".join(field(" IF ", digit_of(div), f' = {k} "{AR[k]}" "" ') for k in range(10)))


def page_number_paragraph():
    hundreds = field(" IF ", page(), ' > 99 "', digit_chars(100), '" "" ')
    tens = field(" IF ", page(), ' > 9 "', digit_chars(10), '" "" ')
    ones = digit_chars(1)
    return ('<w:p><w:pPr><w:bidi/><w:jc w:val="center"/></w:pPr>' + hundreds + tens + ones + "</w:p>")


def ar(n):
    return "".join(AR[int(c)] for c in str(n))


FN_RPR = ('<w:rFonts w:ascii="Traditional Arabic" w:hAnsi="Traditional Arabic" w:cs="Traditional Arabic"/>'
          '<w:rtl/>')


def fix_document(x):
    def ref(m):
        n = int(m.group(1))
        return ('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/>' + FN_RPR + '</w:rPr>'
                f'<w:footnoteReference w:customMarkFollows="1" w:id="{n}"/><w:t>({ar(n)})</w:t></w:r>')
    return re.subn(r'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="(\d+)"/></w:r>',
                   ref, x)


def fix_footnotes(x):
    def note(m):
        n = int(m.group(1))
        body = m.group(2).replace(
            '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>',
            f'<w:r><w:rPr>{FN_RPR}<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
            f'<w:t xml:space="preserve">({ar(n)}) </w:t></w:r>', 1)
        return f'<w:footnote w:id="{n}">{body}</w:footnote>'
    return re.subn(r'<w:footnote w:id="(\d+)">(.*?)</w:footnote>', note, x, flags=re.S)


def main():
    path = Path(sys.argv[1])
    tmp = path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        n = 0
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                x, k = fix_document(data.decode("utf-8"))
                print(f"footnote references: {k}")
                data = x.encode("utf-8")
            elif item.filename == "word/footnotes.xml":
                x, k = fix_footnotes(data.decode("utf-8"))
                data = x.encode("utf-8")
            elif re.match(r"word/footer\d*\.xml$", item.filename):
                x = data.decode("utf-8")
                new, k = re.subn(r"<w:p\b(?:(?!<w:p\b).)*?PAGE(?:(?!<w:p\b).)*?</w:p>", page_number_paragraph(), x,
                                 count=1, flags=re.S)
                n += k
                data = new.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)
    print(f"footer page numbers replaced in {n} footer(s)")


if __name__ == "__main__":
    main()
