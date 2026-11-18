"""Original synthetic plans. No external image rights or production geometry implied."""
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parents[1]
FONT=Path('C:/Windows/Fonts/arial.ttf')
if not FONT.exists(): FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
pdfmetrics.registerFont(TTFont('Plan',str(FONT)))
PLANS=[
 ('studio','Студия',1,6,6,[('Кухня-гостиная',0,2,6,4),('Прихожая',0,0,3.6,2),('Санузел',3.6,0,2.4,2)]),
 ('two-room','Двухкомнатная квартира',2,9,8,[('Гостиная',0,4,4.5,4),('Спальня',4.5,4,4.5,4),('Коридор',0,2.2,9,1.8),('Кухня',0,0,6,2.2),('Санузел',6,0,3,2.2)]),
 ('three-room','Трёхкомнатная квартира',3,11,9,[('Гостиная',0,4,4,5),('Спальня 1',4,4,3.5,5),('Спальня 2',7.5,4,3.5,5),('Коридор',0,2.5,11,1.5),('Кухня',0,0,5.5,2.5),('Ванная',5.5,0,3,2.5),('Санузел',8.5,0,2.5,2.5)])]
def build():
 out=ROOT/'tests/fixtures/plans'; previews=ROOT/'static/plans';out.mkdir(parents=True,exist_ok=True);previews.mkdir(parents=True,exist_ok=True)
 manifest=[]
 for key,title,count,w,h,rooms in PLANS:
  name='typical-'+key; pdf=out/(name+'.pdf');c=canvas.Canvas(str(pdf),pagesize=(1000,1000));c.setTitle(title+' | ESEPTEP')
  c.setFillColorRGB(.97,.98,.99);c.rect(0,0,1000,1000,fill=1,stroke=0);c.setFillColorRGB(.08,.13,.21);c.setFont('Plan',26);c.drawString(65,945,title)
  c.setFont('Plan',12);c.drawString(65,920,'ESEPTEP · собственная демонстрационная схема · не рабочий проект')
  scale=min(790/w,540/h);ox=(1000-w*scale)/2;oy=340
  # Draw all wall polygons first so a later room cannot close an earlier door opening.
  for _,x,y,rw,rh in rooms:
   c.setFillColorRGB(1,1,1);c.setStrokeColorRGB(.15,.2,.26);c.setLineWidth(5);c.rect(ox+x*scale,oy+y*scale,rw*scale,rh*scale,fill=1,stroke=1)
  truths=[]
  for i,(label,x,y,rw,rh) in enumerate(rooms,1):
   X,Y=ox+x*scale,oy+y*scale;W,H=rw*scale,rh*scale
   area=round(rw*rh,2); truths.append({'name':label,'area':area,'kind':'bathroom' if label in ('Ванная','Санузел') else 'other','page':1})
   c.setFillColorRGB(.1,.18,.3);c.setFont('Plan',13);c.drawCentredString(X+W/2,Y+H/2+8,f'{i}. {label}');c.setFont('Plan',17);c.drawCentredString(X+W/2,Y+H/2-15,f'{area:g} м²')
   c.setFont('Plan',9);c.setFillColorRGB(.38,.43,.5);c.drawCentredString(X+W/2,Y+15,f'{rw:g} × {rh:g} м')
   # Door opening at a circulation-facing edge, with leaf and swing.
   if label not in ('Коридор','Прихожая'):
    dy=Y if y>=4 or (key=='studio' and y==2) else Y+H
    dx=X+min(W*.3,W-45);d=min(40,W*.22)
    c.setStrokeColorRGB(1,1,1);c.setLineWidth(7);c.line(dx,dy,dx+d,dy)
    c.setStrokeColorRGB(.25,.3,.35);c.setLineWidth(1);direction=1 if dy==Y else -1;c.line(dx,dy,dx,dy+direction*d)
    c.arc(dx-d,dy-d,dx+d,dy+d,startAng=0 if direction==1 else 270,extent=90)
   if y+rh==h:
    c.setStrokeColorRGB(.25,.45,.7);c.setLineWidth(2);c.line(X+W*.25,Y+H,X+W*.75,Y+H);c.line(X+W*.25,Y+H-5,X+W*.75,Y+H-5)
  # Entry opening and outer dimensions.
  c.setStrokeColorRGB(1,1,1);c.setLineWidth(8);c.line(ox+15,oy,ox+55,oy);c.setStrokeColorRGB(.25,.3,.35);c.setLineWidth(1);c.line(ox+15,oy,ox+15,oy+40)
  c.setFont('Plan',12);c.setFillColorRGB(.1,.18,.3);c.drawCentredString(500,oy+h*scale+20,f'{w:g} м');c.drawString(ox-42,oy+h*scale/2,f'{h:g} м')
  c.setFont('Plan',17);c.drawString(65,285,'Экспликация помещений');c.drawRightString(935,285,f'Общая площадь: {w*h:g} м²')
  c.setFont('Plan',12)
  for i,r in enumerate(truths,1):
   yy=260-(i-1)*24;c.drawString(65,yy,f'{i:02d}  {r["name"]}');c.drawRightString(935,yy,f'{r["area"]:g} м²')
  c.setFont('Plan',10);c.setFillColorRGB(.4,.45,.5);c.drawString(65,45,'Схема создана для проверки распознавания. Размеры условные, площади — эталон теста.');c.save()
  doc=pdfium.PdfDocument(str(pdf));page=doc[0];bitmap=page.render(scale=1.4);bitmap.to_pil().save(previews/(name+'.png'));bitmap.close();page.close();doc.close()
  manifest.append({'key':key,'title':title,'rooms':count,'area':w*h,'pdf':name+'.pdf','preview':'plans/'+name+'.png','ground_truth':truths,'source':'Original ESEPTEP synthetic drawing, 2026-11-18; repository project asset'})
 (out/'typical-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':build()
