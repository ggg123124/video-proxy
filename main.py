from fastapi import FastAPI, Query, HTTPException
import httpx
import re
import json
from typing import Optional
import uvicorn
from fastapi import Response
app = FastAPI()

# ========== 工具函数：av -> bv 转换 ==========
XOR_CODE = 23442827791579
MAX_AID = 1 << 51
BASE = 58
DATA = 'FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf'

def av2bv(av: str) -> str:
    aid = av[2:] if av.startswith("av") else av
    bytes_list = ['B', 'V', '1', '0', '0', '0', '0', '0', '0', '0', '0', '0']
    bv_index = len(bytes_list) - 1
    tmp = (MAX_AID | int(aid)) ^ XOR_CODE
    while tmp > 0:
        bytes_list[bv_index] = DATA[tmp % BASE]
        tmp //= BASE
        bv_index -= 1
    # swap
    bytes_list[3], bytes_list[9] = bytes_list[9], bytes_list[3]
    bytes_list[4], bytes_list[7] = bytes_list[7], bytes_list[4]
    return ''.join(bytes_list)

async def parse_bilibili_video(url: str) -> str:
    bv_id = None
    if "BV" in url:
        match = re.search(r'BV[^/?&#]+', url)
        bv_id = match.group(0) if match else None
    elif "av" in url:
        match = re.search(r'av\d+', url, re.I)
        if match:
            bv_id = av2bv(match.group(0))

    if not bv_id:
        raise ValueError("无法提取视频编号")

    # 模拟浏览器的 headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.bilibili.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    async with httpx.AsyncClient(headers=headers) as client:
        info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        info_res = await client.get(info_url)
        info_res.raise_for_status()
        video_data = info_res.json()
        cid = video_data["data"].get("cid")
        if not cid:
            raise ValueError("获取 cid 失败")

        play_url = (
            f"https://api.bilibili.com/x/player/playurl"
            f"?bvid={bv_id}&cid={cid}&qn=116&type=&otype=json"
            f"&platform=html5&high_quality=1"
        )
        play_res = await client.get(play_url)
        play_res.raise_for_status()
        play_data = play_res.json()

        video_url = play_data["data"]["durl"][0]["url"]

        if not video_url:
            raise ValueError("无法获取视频直链")

        return video_url

@app.get("/proxy")
async def proxy(url: Optional[str] = Query(None)):
    if not url:
        raise HTTPException(status_code=400, detail="Missing URL parameter")

    # 更完整的浏览器请求头模拟
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    try:
        if "bilibili.com" in url:
            final_url = await parse_bilibili_video(url)
            return Response(status_code=302, headers={"Location": final_url})
        else:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=10.0)
                res.raise_for_status()  # 检查是否有错误状态码
                body_text = res.text

                # 匹配 playAddr JSON 对象
                match = re.search(r'"playAddr":\{.*?\}', body_text, re.DOTALL)
                if not match:
                    raise HTTPException(status_code=404, detail="No playAddr JSON object found in the HTML.")

                play_addr_str = match.group(0)
                play_addr_json = json.loads("{" + play_addr_str + "}")
                video_url = play_addr_json.get("playAddr", {}).get("ori_m3u8")

                if not video_url:
                    raise HTTPException(status_code=404, detail="Video URL not found in the response.")

                return Response(status_code=302, headers={"Location": final_url})
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error occurred: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
# =====================
# ✅ main 函数入口
# =====================
def main():
    uvicorn.run(
        app="main:app",  # 注意这里要匹配你的模块名（即文件名）
        host="127.0.0.1",
        port=8000,
        # reload=True,     # 开发模式下启用热重载
        log_level="info"
    )

if __name__ == "__main__":
    main()