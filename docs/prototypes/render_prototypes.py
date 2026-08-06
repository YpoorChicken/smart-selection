from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1440, 900
OUT = Path(__file__).parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

C = {
    "primary": "#4F46E5", "primary_hover": "#4338CA", "primary_subtle": "#EEF2FF",
    "ink": "#111827", "secondary": "#374151", "muted": "#6B7280",
    "disabled": "#9CA3AF", "canvas": "#F3F4F6", "surface": "#FFFFFF",
    "sunken": "#F9FAFB", "line": "#E5E7EB", "line_strong": "#D1D5DB",
    "success": "#059669", "success_bg": "#ECFDF5", "warning": "#D97706",
    "warning_bg": "#FFFBEB", "danger": "#DC2626", "danger_bg": "#FEF2F2",
    "sidebar": "#111827", "sidebar_hover": "#1F2937", "sidebar_active": "#312E81",
    "sidebar_text": "#D1D5DB", "amazon": "#FF9900", "amazon_bg": "#FFF7ED",
    "shopee": "#EE4D2D", "shopee_bg": "#FEF2F2", "chart2": "#0EA5E9",
}

REG = r"C:\Windows\Fonts\msyh.ttc"
BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size)

def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def label(draw, xy, text, size=14, color=None, bold=False, anchor="la"):
    draw.text(xy, text, font=font(size, bold), fill=color or C["ink"], anchor=anchor)

def card(base, box, radius=8):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((box[0], box[1] + 2, box[2], box[3] + 2), radius, fill=(17, 24, 39, 14))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
    rr(ImageDraw.Draw(base), box, radius, C["surface"], C["line"])

def icon(draw, x, y, kind, color):
    # Restrained 16px line icons; simple geometry keeps the prototype dependency-free.
    if kind == "grid":
        for dx, dy in ((0,0),(9,0),(0,9),(9,9)): draw.rectangle((x+dx,y+dy,x+dx+5,y+dy+5), outline=color, width=2)
    elif kind == "trend":
        draw.line((x,y+13,x+5,y+8,x+10,y+11,x+16,y+2), fill=color, width=2)
    elif kind == "star":
        draw.ellipse((x+2,y+2,x+14,y+14), outline=color, width=2); draw.line((x+5,y+8,x+8,y+11,x+12,y+5),fill=color,width=2)
    elif kind == "box":
        draw.rectangle((x+2,y+4,x+14,y+14), outline=color, width=2); draw.line((x+2,y+7,x+8,y+10,x+14,y+7),fill=color,width=1)
    elif kind == "eye":
        draw.ellipse((x+2,y+5,x+14,y+12), outline=color, width=2); draw.ellipse((x+7,y+7,x+10,y+10),fill=color)
    elif kind == "doc":
        draw.rectangle((x+3,y+2,x+13,y+15), outline=color, width=2); draw.line((x+6,y+7,x+11,y+7),fill=color,width=1); draw.line((x+6,y+10,x+11,y+10),fill=color,width=1)
    else:
        draw.polygon((x+8,y+1,x+15,y+14,x+1,y+14), outline=color); draw.ellipse((x+7,y+6,x+9,y+8),fill=color)

def make_shell():
    im = Image.new("RGBA", (W, H), C["canvas"])
    d = ImageDraw.Draw(im)
    sw, top = 240, 56
    d.rectangle((0, 0, sw, H), fill=C["sidebar"])
    d.line((0, top, sw, top), fill="#293241")
    rr(d, (20, 16, 48, 44), 6, C["primary"])
    label(d, (34, 30), "华", 15, "white", True, "mm")
    label(d, (60, 30), "华普智选", 17, "white", True)

    nav = [
        ("看板", [("运营看板","grid",True)]),
        ("选品分析", [("市场趋势","trend",False),("选品推荐","star",False)]),
        ("运营执行", [("商品管理","box",False),("竞品监控","eye",False),("Listing 优化","doc",False),("库存预警","alert",False)])
    ]
    y = 82
    for group, items in nav:
        label(d, (20, y), group, 11, C["disabled"], True)
        y += 23
        for name, kind, active in items:
            box = (12, y, 228, y + 40)
            if active:
                rr(d, box, 6, C["sidebar_active"])
                d.rectangle((12, y+7, 15, y+33), fill=C["primary"])
            elif name == "市场趋势":
                rr(d, box, 6, C["sidebar_hover"])
            col = "white" if active or name == "市场趋势" else C["sidebar_text"]
            icon(d, 28, y + 12, kind, col)
            label(d, (56, y + 20), name, 14, col, active, "lm")
            if name == "库存预警":
                rr(d, (191, y+10, 215, y+30), 10, C["danger"])
                label(d, (203, y+20), "3", 11, "white", True, "mm")
            y += 44
        y += 15
    d.line((16, H-64, 224, H-64), fill="#293241")
    label(d, (28, H-36), "↪", 16, C["disabled"])
    label(d, (56, H-36), "退出登录", 13, C["sidebar_text"])

    d.rectangle((sw, 0, W, top), fill=C["surface"])
    d.line((sw, top-1, W, top-1), fill=C["line"])
    label(d, (264, 20), "看板 / 运营看板", 11, C["muted"])
    label(d, (264, 43), "运营看板", 21, C["ink"], True, "ls")
    rr(d, (431, 14, 504, 42), 4, C["amazon_bg"], "#FED7AA")
    label(d, (467, 28), "Amazon", 11, C["amazon"], True, "mm")
    rr(d, (512, 14, 559, 42), 4, C["surface"], C["line_strong"])
    label(d, (535, 28), "全部", 12, C["secondary"], False, "mm")
    rr(d, (1178, 16, 1247, 40), 4, C["sunken"], C["line"])
    label(d, (1212, 28), "选品经理", 11, C["secondary"], False, "mm")
    rr(d, (1264, 12, 1296, 44), 16, C["primary_subtle"])
    label(d, (1280, 28), "张", 13, C["primary"], True, "mm")
    label(d, (1310, 28), "张敏", 14, C["ink"], True, "lm")
    label(d, (1362, 28), "⌄", 14, C["muted"], False, "mm")

    x0, gap = 264, 16
    content_w = W - x0 - 24
    cw = (content_w - gap*3)//4
    cards = [
        ("选品待处理","12","较昨日 +3",C["primary"],C["primary_subtle"]),
        ("未读告警","3","需要尽快处理",C["danger"],C["danger_bg"]),
        ("竞品动态","5","近 24 小时",C["success"],C["success_bg"]),
        ("库存风险","2","低于安全库存",C["warning"],C["warning_bg"]),
    ]
    for i, (title, val, sub, accent, bg) in enumerate(cards):
        x = x0 + i*(cw+gap); box = (x, 80, x+cw, 202)
        card(im, box); d = ImageDraw.Draw(im)
        label(d, (x+16, 104), title, 12, C["muted"])
        label(d, (x+16, 151), val, 28, C["ink"], True, "ls")
        rr(d, (x+16, 168, x+115, 190), 4, bg)
        label(d, (x+65, 179), sub, 10, accent, True, "mm")
        label(d, (x+cw-20, 181), "›", 18, C["disabled"], False, "mm")

    left = (264, 226, 750, 560); mid = (766, 226, 1028, 560); right = (1044, 226, 1416, 560)
    for b in (left, mid, right): card(im, b)
    d = ImageDraw.Draw(im)
    label(d, (284, 258), "趋势摘要", 16, C["ink"], True)
    label(d, (284, 281), "近 7 日 · 推荐品类热度", 11, C["muted"])
    for gy in (330, 380, 430, 480):
        d.line((300, gy, 726, gy), fill=C["line"])
    pts = [(306,456),(366,431),(426,443),(486,385),(546,402),(606,344),(666,361),(720,310)]
    d.line(pts, fill=C["primary"], width=3, joint="curve")
    for p in pts: d.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill="white",outline=C["primary"],width=2)
    for i, day in enumerate(("周一","周二","周三","周四","周五","周六","周日")):
        label(d, (310+i*65, 520), day, 10, C["muted"], anchor="mm")

    label(d, (786, 258), "选品进度", 16, C["ink"], True)
    for y, name, value, color, ratio in [
        (318,"待审","12",C["primary"],.72),(388,"已接受","28",C["success"],.88),(458,"已拒绝","7",C["danger"],.34)
    ]:
        label(d,(786,y),name,12,C["secondary"]); label(d,(1005,y),value,13,C["ink"],True,"ra")
        rr(d,(786,y+18,1007,y+26),4,C["line"]); rr(d,(786,y+18,786+int(221*ratio),y+26),4,color)

    label(d, (1064, 258), "竞品动态", 16, C["ink"], True)
    label(d, (1388, 258), "查看全部", 11, C["primary"], False, "ra")
    rows = [
        ("无线降噪耳机","价格下调","-6.2%",C["danger"]),
        ("便携榨汁杯","排名上升","+12",C["success"]),
        ("宠物饮水机","库存不足","8 件",C["warning"]),
        ("硅胶厨具套装","新增评价","+24",C["success"]),
    ]
    ry=306
    for name,status,num,col in rows:
        d.line((1064,ry-14,1396,ry-14),fill=C["line"])
        rr(d,(1064,ry-1,1096,ry+31),6,C["sunken"])
        label(d,(1110,ry+7),name,12,C["ink"],True)
        label(d,(1110,ry+25),status,10,C["muted"])
        label(d,(1392,ry+16),num,12,col,True,"rm")
        ry += 58

    card(im, (264, 584, 1416, 854))
    d = ImageDraw.Draw(im)
    label(d,(284,616),"库存预警",16,C["ink"],True)
    label(d,(1388,616),"共 2 项风险",11,C["warning"],False,"ra")
    d.rectangle((284,642,1396,678),fill=C["sunken"])
    headers=[("商品",300),("SKU",720),("可用库存",930),("风险等级",1085),("更新时间",1240)]
    for t,x in headers: label(d,(x,660),t,11,C["muted"],True,"lm")
    data=[
        ("折叠旅行收纳包","HP-TR-2048","6","高风险","今天 14:32"),
        ("USB-C 多口充电器","HP-CH-1182","11","中风险","今天 13:08"),
    ]
    yy=700
    for row in data:
        d.line((284,yy+35,1396,yy+35),fill=C["line"])
        label(d,(300,yy),row[0],13,C["ink"],True,"lm"); label(d,(720,yy),row[1],11,C["secondary"],False,"lm")
        label(d,(960,yy),row[2],13,C["ink"],True,"rm")
        bg=C["danger_bg"] if row[3]=="高风险" else C["warning_bg"]; col=C["danger"] if row[3]=="高风险" else C["warning"]
        rr(d,(1085,yy-12,1147,yy+12),4,bg); label(d,(1116,yy),row[3],10,col,True,"mm")
        label(d,(1240,yy),row[4],11,C["muted"],False,"lm")
        yy+=58
    im.convert("RGB").save(OUT / "00-global-shell.png", quality=96)

def make_login():
    im = Image.new("RGBA", (W, H), C["canvas"])
    d = ImageDraw.Draw(im)
    # Minimal brand marker in the page corner; auth card remains the clear focal point.
    rr(d,(40,36,68,64),6,C["primary"]); label(d,(54,50),"华",14,"white",True,"mm")
    label(d,(80,50),"华普智选",15,C["ink"],True,"lm")
    box=(500,112,940,788)
    card(im, box, 12); d=ImageDraw.Draw(im)
    rr(d,(696,154,744,202),10,C["primary"]); label(d,(720,178),"华",23,"white",True,"mm")
    label(d,(720,234),"华普智选",22,C["ink"],True,"mm")
    label(d,(720,265),"智能选品与跨境运营中台",13,C["muted"],False,"mm")
    # Tabs
    label(d,(610,321),"登录",14,C["primary"],True,"mm")
    label(d,(830,321),"注册",14,C["muted"],False,"mm")
    d.line((540,344,900,344),fill=C["line"])
    d.rectangle((540,342,720,344),fill=C["primary"])

    label(d,(540,382),"账号",13,C["secondary"],True)
    rr(d,(540,400,900,444),6,C["surface"],C["line_strong"])
    label(d,(556,422),"邮箱 / 手机号",13,C["disabled"],False,"lm")
    label(d,(540,482),"密码",13,C["secondary"],True)
    rr(d,(540,500,900,544),6,C["surface"],C["line_strong"])
    label(d,(556,522),"请输入密码",13,C["disabled"],False,"lm")
    # Eye icon
    d.ellipse((865,515,884,529),outline=C["muted"],width=1); d.ellipse((872,519,878,525),fill=C["muted"])
    label(d,(900,574),"忘记密码？",12,C["primary"],False,"ra")
    rr(d,(540,602,900,642),6,C["primary"])
    label(d,(720,622),"登录",14,"white",True,"mm")
    d.line((540,682,690,682),fill=C["line"]); d.line((750,682,900,682),fill=C["line"])
    label(d,(720,682),"或",11,C["disabled"],False,"mm")
    label(d,(720,724),"还没有账号？",12,C["muted"],False,"mm")
    label(d,(720,751),"切换上方「注册」Tab 创建账号",12,C["primary"],True,"mm")
    label(d,(720,840),"登录即表示你同意服务条款与隐私政策",11,C["disabled"],False,"mm")
    im.convert("RGB").save(OUT / "01-login.png", quality=96)

def page_shell(active, title, breadcrumb, role, user):
    im = Image.new("RGBA", (W, H), C["canvas"])
    d = ImageDraw.Draw(im)
    sw, top = 220, 56
    d.rectangle((0, 0, sw, H), fill=C["sidebar"])
    d.line((0, top, sw, top), fill="#293241")
    rr(d, (16, 14, 44, 42), 6, C["primary"])
    label(d, (30, 28), "华", 14, "white", True, "mm")
    label(d, (56, 28), "华普智选", 16, "white", True, "lm")
    nav = [
        ("看板", [("运营看板", "grid")]),
        ("选品分析", [("市场趋势", "trend"), ("选品推荐", "star")]),
        ("运营执行", [("商品管理", "box"), ("竞品监控", "eye"), ("Listing 优化", "doc"), ("库存预警", "alert")]),
    ]
    y = 78
    for group, items in nav:
        label(d, (16, y), group, 11, C["disabled"], True)
        y += 22
        for name, kind in items:
            selected = name == active
            box = (8, y, 212, y + 40)
            if selected:
                rr(d, box, 6, C["sidebar_active"])
                d.rectangle((8, y + 7, 11, y + 33), fill=C["primary"])
            col = "white" if selected else C["sidebar_text"]
            icon(d, 22, y + 12, kind, col)
            label(d, (48, y + 20), name, 13, col, selected, "lm")
            if name == "库存预警":
                rr(d, (179, y + 10, 203, y + 30), 10, C["danger"])
                label(d, (191, y + 20), "3", 10, "white", True, "mm")
            y += 43
        y += 13
    d.line((16, H - 60, 204, H - 60), fill="#293241")
    label(d, (24, H - 32), "↪", 15, C["disabled"])
    label(d, (48, H - 32), "退出登录", 12, C["sidebar_text"])
    d.rectangle((sw, 0, W, top), fill=C["surface"])
    d.line((sw, top - 1, W, top - 1), fill=C["line"])
    label(d, (244, 18), breadcrumb, 11, C["muted"])
    label(d, (244, 43), title, 21, C["ink"], True, "ls")
    rr(d, (1196, 16, 1258, 40), 4, C["sunken"], C["line"])
    label(d, (1227, 28), role, 11, C["secondary"], False, "mm")
    rr(d, (1272, 12, 1304, 44), 16, C["primary_subtle"])
    label(d, (1288, 28), user[0], 13, C["primary"], True, "mm")
    label(d, (1318, 28), user, 13, C["ink"], True, "lm")
    label(d, (1378, 28), "⌄", 13, C["muted"], False, "mm")
    return im, ImageDraw.Draw(im)

def spinner(draw, cx, cy, color):
    draw.arc((cx - 7, cy - 7, cx + 7, cy + 7), 25, 285, fill=color, width=2)
    draw.ellipse((cx + 4, cy - 6, cx + 7, cy - 3), fill=color)

def make_products():
    im, d = page_shell("商品管理", "商品管理", "运营执行 / 商品管理", "运营", "李然")
    # Search and filter toolbar.
    card(im, (244, 80, 1416, 150))
    d = ImageDraw.Draw(im)
    rr(d, (260, 96, 530, 132), 6, C["surface"], C["line_strong"])
    label(d, (276, 114), "⌕  搜索标题 / ASIN", 12, C["disabled"], False, "lm")
    for box, text in [
        ((542, 96, 660, 132), "全部平台  ⌄"),
        ((672, 96, 790, 132), "全部品类  ⌄"),
        ((802, 96, 950, 132), "评分从高到低  ⌄"),
    ]:
        rr(d, box, 6, C["surface"], C["line_strong"])
        label(d, ((box[0] + box[2]) // 2, 114), text, 11, C["secondary"], False, "mm")
    d.rectangle((966, 105, 980, 119), outline=C["line_strong"], width=1)
    label(d, (990, 113), "仅看自营关注", 11, C["secondary"], False, "lm")
    rr(d, (1130, 96, 1200, 132), 6, C["surface"], C["line_strong"])
    label(d, (1165, 114), "导出", 12, C["secondary"], False, "mm")
    rr(d, (1212, 96, 1320, 132), 6, C["primary"])
    spinner(d, 1233, 114, "white")
    label(d, (1272, 114), "同步中…", 12, "white", True, "mm")
    label(d, (1332, 108), "状态标注", 10, C["primary"], True)
    label(d, (1332, 126), "loading / 禁止重复提交", 9, C["muted"])
    label(d, (260, 142), "最近同步：今天 16:42", 9, C["muted"])

    # Category tree.
    card(im, (244, 166, 454, 860))
    d = ImageDraw.Draw(im)
    label(d, (260, 194), "品类", 16, C["ink"], True)
    label(d, (434, 194), "共 24", 10, C["muted"], False, "ra")
    tree = [
        (218, "⌄  电子产品", "386", 0, False),
        (252, "⌄  耳机", "204", 1, False),
        (286, "无线耳机", "128", 2, True),
        (320, "有线耳机", "76", 2, False),
        (354, "›  手机配件", "182", 1, False),
        (398, "›  家居厨房", "316", 0, False),
        (432, "›  宠物用品", "147", 0, False),
        (466, "›  户外运动", "94", 0, False),
    ]
    for y, name, count, depth, selected in tree:
        if selected:
            rr(d, (252, y - 17, 438, y + 17), 4, C["primary_subtle"])
            d.rectangle((252, y - 11, 255, y + 11), fill=C["primary"])
        label(d, (260 + depth * 15, y), name, 12, C["primary"] if selected else C["secondary"], selected, "lm")
        label(d, (426, y), count, 10, C["muted"], False, "rm")
    # Empty state specimen.
    rr(d, (258, 550, 440, 832), 6, C["sunken"], C["line"])
    label(d, (270, 572), "状态标注 · 空状态", 10, C["primary"], True)
    d.rectangle((334, 625, 364, 650), outline=C["disabled"], width=2)
    d.line((334, 632, 349, 640, 364, 632), fill=C["disabled"], width=1)
    label(d, (349, 684), "还没有同步商品", 13, C["ink"], True, "mm")
    label(d, (349, 711), "去配置采集任务后再同步", 10, C["muted"], False, "mm")
    rr(d, (301, 738, 397, 772), 6, C["primary"])
    label(d, (349, 755), "配置采集", 11, "white", True, "mm")
    label(d, (349, 798), "单色图标 · 一句说明 · 单一操作", 9, C["disabled"], False, "mm")

    # Product table.
    card(im, (470, 166, 1416, 860))
    d = ImageDraw.Draw(im)
    label(d, (486, 194), "无线耳机", 16, C["ink"], True)
    label(d, (579, 194), "128 件商品", 10, C["muted"])
    d.rectangle((486, 212, 1400, 250), fill=C["sunken"])
    headers = [("商品", 498), ("平台", 800), ("价格", 900), ("评分", 982), ("销量排名", 1055), ("最近同步", 1160), ("操作", 1310)]
    for text, x in headers:
        label(d, (x, 231), text, 10, C["muted"], True, "lm")
    rows = [
        ("无线降噪耳机 Pro", "B0C8H7Q2K9", "Amazon", "$59.99", "4.7", "#1,284", "今天 16:42"),
        ("运动蓝牙耳机 IPX7", "B0B3X9L5M2", "Shopee", "$32.50", "4.3", "#3,016", "今天 16:40"),
        ("开放式耳夹耳机", "B0D1K6P8R4", "Amazon", "$45.00", "3.8", "#6,721", "今天 16:38"),
        ("儿童音量保护耳机", "B09V4M2N7S", "Amazon", "$24.99", "4.6", "#2,105", "今天 16:35"),
        ("真无线游戏耳机", "B0C2F8J4T6", "Shopee", "$39.90", "4.1", "#4,892", "今天 16:31"),
        ("商务通话降噪耳机", "B0A7N3W9Q1", "Amazon", "$79.00", "4.8", "#986", "今天 16:28"),
    ]
    y = 278
    for i, row in enumerate(rows):
        d.line((486, y + 31, 1400, y + 31), fill=C["line"])
        rr(d, (498, y - 20, 538, y + 20), 5, "#EEF2F7", C["line"])
        d.ellipse((508, y - 10, 528, y + 10), outline="#94A3B8", width=2)
        d.arc((502, y - 15, 534, y + 17), 190, 350, fill="#64748B", width=2)
        label(d, (550, y - 6), row[0], 12, C["ink"], True, "lm")
        label(d, (550, y + 13), row[1], 9, C["muted"], False, "lm")
        is_amz = row[2] == "Amazon"
        rr(d, (790, y - 11, 846, y + 11), 4, C["amazon_bg"] if is_amz else C["shopee_bg"])
        label(d, (818, y), row[2], 9, C["amazon"] if is_amz else C["shopee"], True, "mm")
        label(d, (944, y), row[3], 12, C["primary"], True, "rm")
        score = float(row[4])
        score_col = C["success"] if score >= 4.5 else C["warning"] if score >= 4.0 else C["danger"]
        label(d, (1010, y), "★ " + row[4], 11, score_col, True, "rm")
        label(d, (1118, y), row[5], 11, C["secondary"], False, "rm")
        label(d, (1160, y), row[6], 10, C["muted"], False, "lm")
        label(d, (1302, y), "详情", 10, C["primary"], False, "lm")
        label(d, (1342, y), "价格历史", 10, C["primary"], False, "lm")
        y += 61
    label(d, (486, 830), "共 128 条", 10, C["muted"])
    rr(d, (1298, 812, 1334, 840), 4, C["surface"], C["line"])
    label(d, (1316, 826), "‹", 12, C["disabled"], False, "mm")
    rr(d, (1340, 812, 1376, 840), 4, C["primary"])
    label(d, (1358, 826), "1", 11, "white", True, "mm")
    rr(d, (1382, 812, 1400, 840), 4, C["surface"], C["line"])
    label(d, (1391, 826), "›", 12, C["secondary"], False, "mm")

    # Price history modal specimen over the lower table.
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((880, 440, 1400, 808), radius=8, fill=(17, 24, 39, 38))
    im.alpha_composite(overlay)
    card(im, (900, 420, 1384, 790), 8)
    d = ImageDraw.Draw(im)
    label(d, (920, 449), "状态标注 · 价格历史弹窗", 10, C["primary"], True)
    label(d, (920, 478), "无线降噪耳机 Pro", 15, C["ink"], True)
    label(d, (1360, 462), "×", 17, C["muted"], False, "mm")
    label(d, (920, 503), "近 30 天 · Amazon 美国站", 10, C["muted"])
    for gy in (548, 598, 648):
        d.line((938, gy, 1348, gy), fill=C["line"])
    pts = [(946, 630), (1000, 614), (1055, 620), (1110, 578), (1165, 590), (1220, 552), (1275, 566), (1338, 526)]
    d.line(pts, fill=C["primary"], width=3, joint="curve")
    for p in pts:
        d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="white", outline=C["primary"], width=2)
    metrics = [("当前价", "$59.99"), ("最低价", "$51.20"), ("最高价", "$67.80")]
    for i, (name, value) in enumerate(metrics):
        x = 936 + i * 137
        label(d, (x, 692), name, 9, C["muted"])
        label(d, (x, 718), value, 13, C["ink"], True)
    rr(d, (1288, 742, 1356, 772), 6, C["surface"], C["line_strong"])
    label(d, (1322, 757), "关闭", 11, C["secondary"], False, "mm")
    im.convert("RGB").save(OUT / "02-products.png", quality=96)

def gradient_box(im, box, start, end, radius=8):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    s = tuple(int(start[i:i+2], 16) for i in (1, 3, 5))
    e = tuple(int(end[i:i+2], 16) for i in (1, 3, 5))
    width = max(1, box[2] - box[0])
    for x in range(box[0], box[2] + 1):
        t = (x - box[0]) / width
        col = tuple(round(s[j] + (e[j] - s[j]) * t) for j in range(3)) + (255,)
        ld.line((x, box[1], x, box[3]), fill=col)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    layer.putalpha(mask)
    im.alpha_composite(layer)
    ImageDraw.Draw(im).rounded_rectangle(box, radius=radius, outline="#C7D2FE", width=1)

def make_trends():
    im, d = page_shell("市场趋势", "市场趋势", "选品分析 / 市场趋势", "选品经理", "张敏")
    card(im, (244, 80, 1416, 140))
    d = ImageDraw.Draw(im)
    label(d, (260, 110), "趋势筛选", 12, C["secondary"], True, "lm")
    for box, text in [
        ((344, 92, 434, 128), "Amazon  ⌄"),
        ((446, 92, 568, 128), "近 12 个月  ⌄"),
        ((580, 92, 682, 128), "美国站  ⌄"),
    ]:
        rr(d, box, 6, C["surface"], C["line_strong"])
        label(d, ((box[0] + box[2]) // 2, 110), text, 11, C["secondary"], False, "mm")
    label(d, (702, 110), "更新于今天 16:30", 10, C["muted"], False, "lm")
    rr(d, (1248, 92, 1400, 128), 6, C["primary"])
    label(d, (1324, 110), "查看相关推荐  →", 11, "white", True, "mm")

    # 40% category table.
    left = (244, 156, 706, 860)
    card(im, left)
    d = ImageDraw.Draw(im)
    label(d, (262, 186), "品类趋势", 16, C["ink"], True)
    label(d, (686, 186), "共 24 个品类", 10, C["muted"], False, "ra")
    d.rectangle((260, 204, 690, 242), fill=C["sunken"])
    for text, x in [("品类", 276), ("均价", 460), ("月增长率", 530), ("热度", 632)]:
        label(d, (x, 223), text, 10, C["muted"], True, "lm")
    rows = [
        ("无线耳机", "$48.72", "▲ 18.6%", "高", True),
        ("便携榨汁杯", "$29.10", "▲ 12.4%", "高", False),
        ("宠物饮水机", "$35.80", "▲ 8.9%", "中", False),
        ("硅胶厨具", "$22.60", "▼ 3.1%", "中", False),
        ("旅行收纳", "$19.40", "▲ 5.7%", "中", False),
        ("桌面加湿器", "$31.20", "▼ 7.2%", "低", False),
        ("智能跳绳", "$26.90", "▲ 4.3%", "中", False),
    ]
    y = 269
    for i, (name, price, growth, heat, selected) in enumerate(rows):
        if selected:
            d.rectangle((260, y - 23, 690, y + 23), fill=C["primary_subtle"])
            d.rectangle((260, y - 18, 263, y + 18), fill=C["primary"])
        d.line((260, y + 23, 690, y + 23), fill=C["line"])
        label(d, (276, y), ("⌄  " if selected else "›  ") + name, 11, C["primary"] if selected else C["ink"], selected, "lm")
        label(d, (500, y), price, 11, C["secondary"], False, "rm")
        col = C["success"] if growth.startswith("▲") else C["danger"]
        label(d, (603, y), growth, 11, col, True, "rm")
        heat_col = C["success"] if heat == "高" else C["warning"] if heat == "中" else C["muted"]
        rr(d, (634, y - 10, 672, y + 10), 4, C["success_bg"] if heat == "高" else C["warning_bg"] if heat == "中" else C["sunken"])
        label(d, (653, y), heat, 9, heat_col, True, "mm")
        y += 47
        if selected:
            rr(d, (272, y - 12, 680, y + 100), 4, C["sunken"], C["line"])
            label(d, (288, y + 8), "展开详情", 10, C["primary"], True)
            details = [("销量指数", "86 / 100"), ("竞争强度", "中等"), ("季节性", "Q4 旺季")]
            for j, (k, v) in enumerate(details):
                x = 288 + j * 122
                label(d, (x, y + 36), k, 9, C["muted"])
                label(d, (x, y + 58), v, 11, C["ink"], True)
            label(d, (288, y + 86), "连续 4 个月增长，核心需求集中在 $40–60。", 10, C["secondary"])
            y += 125
    label(d, (262, 834), "点击行展开详情 · 同时刷新右侧图表", 9, C["muted"])

    # Right 60%: price distribution.
    right_x, right_w = 722, 694
    card(im, (right_x, 156, 1416, 382))
    d = ImageDraw.Draw(im)
    label(d, (742, 184), "价格分布", 16, C["ink"], True)
    label(d, (742, 205), "无线耳机 · 近 12 个月商品样本", 10, C["muted"])
    chart = (770, 230, 1388, 350)
    for gy in (250, 285, 320, 350):
        d.line((chart[0], gy, chart[2], gy), fill=C["line"])
    vals = [42, 88, 116, 67, 31]
    labels_x = ["$0–20", "$20–40", "$40–60", "$60–80", "$80+"]
    for i, val in enumerate(vals):
        x = 804 + i * 116
        h = int(val * 0.82)
        col = C["chart2"] if i == 2 else C["primary"]
        rr(d, (x, 350 - h, x + 54, 350), 3, col)
        label(d, (x + 27, 365), labels_x[i], 9, C["muted"], False, "mm")
        label(d, (x + 27, 342 - h), str(val), 9, C["secondary"], True, "mm")
    # Tooltip.
    rr(d, (1018, 222, 1136, 270), 5, C["surface"], C["line"])
    label(d, (1030, 240), "$40–60", 9, C["muted"])
    label(d, (1030, 258), "商品数 116", 10, C["ink"], True)

    # Growth line chart.
    card(im, (right_x, 398, 1416, 650))
    d = ImageDraw.Draw(im)
    label(d, (742, 426), "月度增长趋势", 16, C["ink"], True)
    label(d, (1388, 426), "当前  ▲ 18.6%", 11, C["success"], True, "ra")
    label(d, (742, 447), "品类增长", 9, C["primary"], True)
    label(d, (810, 447), "市场基准", 9, C["chart2"], True)
    for gy in (480, 520, 560, 600):
        d.line((770, gy, 1388, gy), fill=C["line"])
    p1 = [(780, 582), (830, 570), (880, 576), (930, 548), (980, 555), (1030, 520), (1080, 530), (1130, 500), (1180, 510), (1230, 475), (1280, 486), (1372, 458)]
    p2 = [(780, 590), (830, 584), (880, 580), (930, 572), (980, 567), (1030, 560), (1080, 548), (1130, 544), (1180, 538), (1230, 526), (1280, 521), (1372, 514)]
    d.line(p1, fill=C["primary"], width=3, joint="curve")
    d.line(p2, fill=C["chart2"], width=2, joint="curve")
    for p in p1[::2]:
        d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="white", outline=C["primary"], width=2)
    for i, m in enumerate(("9月", "10月", "11月", "12月", "1月", "2月", "3月")):
        label(d, (785 + i * 98, 626), m, 9, C["muted"], False, "mm")

    # AI report card, gradient limited to this card.
    gradient_box(im, (right_x, 666, 1416, 860), "#EFF6FF", "#F5F3FF", 8)
    d = ImageDraw.Draw(im)
    rr(d, (742, 686, 770, 714), 6, C["primary"])
    label(d, (756, 700), "AI", 9, "white", True, "mm")
    label(d, (782, 700), "AI 趋势解读", 16, C["ink"], True, "lm")
    label(d, (1388, 700), "重新解读", 10, C["primary"], False, "ra")
    label(d, (742, 739), "无线耳机连续 4 个月增长，$40–60 价格带需求最集中；", 12, C["secondary"])
    label(d, (742, 765), "竞争强度中等，建议关注 Q4 备货窗口，并优先验证降噪与开放式产品。", 12, C["secondary"])
    rr(d, (742, 790, 852, 816), 4, C["warning_bg"])
    label(d, (797, 803), "季节性：Q4 旺季", 9, C["warning"], True, "mm")
    label(d, (742, 840), "生成于今天 16:31 · 基于 1,284 个商品样本", 9, C["muted"])
    label(d, (1388, 840), "loading → 180ms 淡入", 9, C["primary"], True, "ra")
    im.convert("RGB").save(OUT / "03-trends.png", quality=96)

if __name__ == "__main__":
    make_shell()
    make_login()
    make_products()
    make_trends()
    print("generated:", *(p.name for p in sorted(OUT.glob("*.png"))))
