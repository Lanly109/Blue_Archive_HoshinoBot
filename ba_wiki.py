import base64
import os
import json
import datetime

import hoshino
import hashlib
from hoshino import aiorequests,R

sv = hoshino.Service('ba_wiki', enable_on_default=True, visible=True, bundle='ba_wiki')

base_path = "bluearchive/wiki/"

arona_url = "https://arona.diyigemt.com/api/v1/image"
arona_img_url = "https://arona.cdn.diyigemt.com/image"
base_url = "https://ba.gamekee.com/v1/content/detail/"
battle_url = "http://ba.gamerhub.cn/api/get_ba_raid_ranking_data?season={}&ranking=1,2001,20001,30001"
battle_season_file = "current_battle_season.json"

urls = {
    "cn_pools": "596691",
    "global_pools": "150045",
}

if not os.path.exists(battle_season_file):
    battle_season = {}
else:
    with open(battle_season_file, "r") as f:
        battle_season = json.load(f);

def get_battle_score(result, ranks):
    msg = ''
    for rank in ranks:
        score = next((item[1] for item in reversed(result[str(rank)]) if item[1] is not None), None)
        msg += f'第{rank}名: \t{score}\n'
    return msg.strip()

server_list = ['cn', 'jp', 'global']

@sv.on_prefix(("ba总力战"))
async def set_battle_score(bot, ev):
    cmd = ev.message.extract_plain_text().strip().split()
    server = cmd[0]
    season = cmd[1]
    if server not in server_list:
        await bot.finish(ev, f"未知的服务器{server}，支持{' '.join(server_list)}")
    battle_season[server] = season
    with open(battle_season_file, "w") as f:
        f.write(json.dumps(battle_season))
    await bot.finish(ev, f"{server}切换为第{season}期")

@sv.on_prefix(("ba档线"))
async def send_battle_score(bot, ev):
    server = ev.message.extract_plain_text().strip() or 'cn'
    if server not in server_list:
        await bot.finish(ev, f"未知的服务器{server}，支持{' '.join(server_list)}")
    if server not in battle_season:
        await bot.finish(ev, "请先发送[ba总力战 {server} 3]设置总力战档期")
    url = battle_url.format(battle_season[server])
    text = f"蔚蓝档案{server}服 第{battle_season[server]}期\n"
    try:
        res = await (await aiorequests.get(url)).json()
        text += f'官服:{datetime.datetime.fromtimestamp(res["lastUpdatedTime"])}\n' + get_battle_score(res['data'], [1, 2001, 20001]) + '\n\n'
        text += f'B服:{datetime.datetime.fromtimestamp(res["lastUpdatedTime_bilibili"])}\n' + get_battle_score(res['data_bilibili'], [1, 1001, 8001])
    except Exception as e:
        sv.logger.error(str(e))
        text += f"获取档线失败:{str(e)}"

    await bot.finish(ev, text)

async def im2base64str(img_url):
    img = await aiorequests.get(img_url, timeout=5)
    img_cont = await img.content
    base64_str = f"base64://{base64.b64encode(img_cont).decode()}"
    return base64_str


async def get_pools(server="cn"):
    url = base_url + urls[server + "_pools"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Game-Alias": "ba"}
    r = await aiorequests.get(url, headers=headers)
    data = await r.json()
    msgs = []
    try:
        thumb = data["data"]["thumb"]
        thumb_urls = thumb.split(",")
        for thumb_url in thumb_urls:
            img_url = "https:" + thumb_url.strip("")
            b64img = await im2base64str(img_url)
            msgs.append(f"\n[CQ:image,file={b64img}]")
        if len(thumb_urls) == 0:
            for thumb_url in data["data"]["thumb_list"]:
                img_url = "https:" + thumb_url
                b64img = await im2base64str(img_url)
                msgs.append(f"\n[CQ:image,file={b64img}]")
    except Exception as e:
        msgs.append("获取千里眼图片失败")
        print(e)
    return msgs


@sv.on_fullmatch(("国服千里眼", "国服万里眼","国服未来视"))
async def send_pools_cn(bot, ev):
    server = "cn"
    msgs = await get_pools(server)
    for msg in msgs:
        await bot.send(ev, msg)

@sv.on_fullmatch(("国际服千里眼","国际服未来视"))
async def send_pools_cn(bot, ev):
    server = "global"
    msgs = await get_pools(server)
    for msg in msgs:
        await bot.send(ev, msg)

def get_file_md5(file_path):
    with open(file_path, 'rb') as f:
        hash = hashlib.md5(f.read()).hexdigest()
        return hash


async def get_arona_img(name):
    msgs = []
    try:
        r = await aiorequests.get(arona_url, params={"name": name}, timeout=10)
        data = await r.json()
        if data["status"] != 200 and data["status"] != 101:
            msgs.append("请求错误")
            print(data)
            return msgs
        if len(data["data"]) == 0:
            msgs.append("未找到相关内容")
            return msgs
        if data["message"] == "fuse search":
            msgs = await get_arona_img(data["data"][0]["name"])
            msg = "其他可能的查询结果："
            for item in data["data"][1:]:
                msg += f'\n{item["name"]}'
            msgs.append(msg)
            return msgs

        msgs.append(f"查询结果：{data['data'][0]['name']}")
        path = data["data"][0]["path"]
        hash = data["data"][0]["hash"]

        flag = True
        if R.img(base_path + path).exist:
            local_hash = get_file_md5(R.img(base_path + path).path)
            if local_hash == hash:
                flag = False
        if flag:
            # 判断文件夹是否存在
            target_dir = os.path.dirname(R.img(base_path + path).path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            #获取和保存图片
            img_url = arona_img_url + path
            r = await aiorequests.get(img_url, timeout=10)
            img_cont = await r.content
            with open(R.img(base_path + path).path, 'wb') as f:
                f.write(img_cont)

        msgs.append(R.img(base_path + path).cqcode)


    except Exception as e:
        print(e)
        msgs.append("查询失败")
    return msgs


@sv.on_prefix(("ba攻略", "攻略查询", "/攻略"))
async def send_arona(bot, ev):
    cmd = ev.message.extract_plain_text().strip()
    if not cmd:
        await bot.send(ev, "请输入要查询的内容")
        return
    msgs = await get_arona_img(cmd)
    for msg in msgs:
        await bot.send(ev, msg)
