import requests
from pathlib import Path


# cam-centre: http://192.168.0.100/videoset
# cam-left: http://192.168.0.101/videoset
# cam-right: http://192.168.0.102/videoset
BOUNDARY = "----recctechformboundary"
BASE_URL = {
    "cam_1": "http://192.168.0.100",
    "cam_2": "http://192.168.0.102",
    "cam_3": "http://192.168.0.101",
}
CAM_SETTINGS_DIR = Path(__file__).parent / "config" / "cameras"
SETTINGS = {
    "cam_1": (CAM_SETTINGS_DIR / "cam_1.txt").read_text(),
    "cam_2": (CAM_SETTINGS_DIR / "cam_2.txt").read_text(),
    "cam_3": (CAM_SETTINGS_DIR / "cam_3.txt").read_text(),
}


def main() -> None:
    password = input("BirdDog password: ")
    for cam in ["cam_1", "cam_2", "cam_3"]:
        print(f"Setting up {cam.replace('_', ' ')}")
        with requests.Session() as s:
            s.post(
                f"{BASE_URL[cam]}/login",
                data=f"auth_password={password}",
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cookie": "mod_sel=none; av_settings=none; exp_settings=block; wb_settings=none; pic1_settings=none; pic2_settings=none; cm_settings=none; ci_settings=none; cex_settings=none",
                    "Host": BASE_URL[cam][len("http://"):],
                    "Origin": BASE_URL[cam],
                    "Priority": "u=0, i",
                    "Referer": f"{BASE_URL[cam]}/login",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
                }
            )
            response = s.post(
                f"{BASE_URL[cam]}/videoset",
                data=SETTINGS[cam],
                headers={
                    "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
                },
                cookies={
                    "BirdDogSession": "tOldLgBtXZSunYNCqerDsdKXyIjvNMXWQYVPrkfACiYiyhrvhFBkqvEoFAGqVAXFNuDLKWtJtJEIavaHRupJetxPUgJWCTVqjzHf"
                }
            )


if __name__ == "__main__":
    main()
