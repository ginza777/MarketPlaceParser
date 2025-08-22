import requests
from apps.birbir.models import SiteToken


def check_token():
    token = SiteToken.objects.first()
    print(10*'--+')
    print(token)
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'uz-UZ,uz;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6,en;q=0.5',
        'authorization': '',
        'dnt': '1',
        'origin': 'https://birbir.uz',
        'priority': 'u=1, i',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'x-current-language': 'uz',
        'x-current-region': 'toshkent',
    }
    headers['authorization'] = str(token)

    response = requests.get('https://api.birbir.uz/api/frontoffice/1.3.2.0/user', headers=headers)

    if response.status_code == 401:
        print("[!] Token muddati tugagan, yangi token olish zarur.")
        token.refreshtoken()
        response_new = requests.get('https://api.birbir.uz/api/frontoffice/1.3.2.0/user', headers=headers)
        if response_new.status_code == 200:
            print("[+] Yangi token muvaffaqiyatli yangilandi.")
            return True,token
        else:
            print("[!] Yangi token olishda xatolik:", response_new.status_code, response_new.text)
            return False,None

    elif response.status_code == 200:
        print("[+] Token to‘g‘ri, hech narsa qilish shart emas.")
        return True,token

    else:
        print(f"[!] Noma'lum xatolik: {response.status_code} - {response.text}")
        return False,None
