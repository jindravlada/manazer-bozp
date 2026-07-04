from pathlib import Path
from zipfile import ZipFile
import html


class OdtExportEngine:
    def render(self, template, output, values):
        with ZipFile(template, "r") as zin, ZipFile(output, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(".xml"):
                    xml = data.decode("utf-8")
                    for key, value in values.items():
                        escaped = html.escape(str(value or ""), quote=False).replace(
                            "\n",
                            "<text:line-break/>",
                        )
                        xml = xml.replace("${" + key + "}", escaped)
                    data = xml.encode("utf-8")
                zout.writestr(item, data)
