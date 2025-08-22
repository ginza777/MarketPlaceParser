# Fayllar nomi
input_file = "proxy.txt"
output_file = "proxy.py"

def generate_proxy_list():
    """
    proxy.txt faylini o'qiydi va proxy.py fayliga ro'yxat ko'rinishida yozadi.
    """
    try:
        # proxy.txt faylini o'qish uchun ochamiz
        with open(input_file, 'r') as f_in:
            # Har bir qatorni o'qib, bo'shliqlarni olib tashlaymiz
            proxies = [line.strip() for line in f_in if line.strip()]

        # proxy.py faylini yozish uchun ochamiz
        with open(output_file, 'w') as f_out:
            # Faylga proxy_list o'zgaruvchisini yozamiz
            f_out.write("proxy_list = [\n")
            for proxy in proxies:
                # Har bir proksini qo'shtirnoq ichida yozamiz
                f_out.write(f"    '{proxy}',\n")
            f_out.write("]\n")

        print(f"Muvaffaqiyatli! {output_file} fayli yaratildi.")
        print(f"Unga {len(proxies)} ta proksi yozildi.")

    except FileNotFoundError:
        print(f"Xatolik: {input_file} fayli topilmadi. Iltimos, uni bir papkaga joylashtiring.")
    except Exception as e:
        print(f"Noma'lum xatolik yuz berdi: {e}")

# Skriptni ishga tushirish
if __name__ == "__main__":
    generate_proxy_list()