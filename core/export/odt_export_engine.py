from pathlib import Path
from zipfile import ZipFile
import html
class OdtExportEngine:
    def render(self,template,output,values):
        with ZipFile(template,'r') as zin, ZipFile(output,'w') as zout:
            for item in zin.infolist():
                data=zin.read(item.filename)
                if item.filename=="content.xml":
                    xml=data.decode("utf-8")
                    for k,v in values.items():
                        t=html.escape(str(v or ""),quote=False).replace("\n","<text:line-break/>")
                        xml=xml.replace("${"+k+"}",t)
                    data=xml.encode("utf-8")
                zout.writestr(item,data)
