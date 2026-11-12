import os
import re
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LYRICS_DIR = os.path.join(BASE_DIR, "v1", "lyrics")
INDEX_FILE = os.path.join(BASE_DIR, "v1", "index.json")

os.makedirs(LYRICS_DIR, exist_ok=True)

USER_AGENT = "HiFiLyricsHarvester/2.0 (https://github.com/saferill/HiFi-lyrics)"
HEADERS = {"User-Agent": USER_AGENT}

INDO_ESSENTIALS = [
    ("Bernadya", "Satu Bulan"), ("Bernadya", "Kata Mereka Ini Berlebihan"), ("Bernadya", "Kini Mereka Tahu"),
    ("Bernadya", "Untungnya, Hidup Harus Tetap Berjalan"), ("Bernadya", "Apa Mungkin"), ("Bernadya", "Masa Sepi"),
    ("Hindia", "Cincin"), ("Hindia", "Evaluasi"), ("Hindia", "Rumah Ke Rumah"), ("Hindia", "Membasuh"),
    ("Hindia", "Secukupnya"), ("Hindia", "Berdansalah, Karir Ini Tak Ada Artinya"), ("Hindia", "Setengah Tahun Ini"),
    ("Sal Priadi", "Gala Bunga Matahari"), ("Sal Priadi", "Dari Planet Lain"), ("Sal Priadi", "Mesra-mesraannya kecil-kecilan dulu"),
    ("Sal Priadi", "Foto kita blur"), ("Sal Priadi", "Kita usahakan rumah itu"), ("Sal Priadi", "Ikat Aku Di Tulang Belikatmu"),
    ("Nadin Amizah", "Rayuan Perempuan Gila"), ("Nadin Amizah", "Bertaut"), ("Nadin Amizah", "Semua Aku Dirayakan"),
    ("Nadin Amizah", "Sorai"), ("Nadin Amizah", "Taruh"), ("Nadin Amizah", "Rumpang"), ("Nadin Amizah", "Ah"),
    ("Denny Caknan", "Cundamani"), ("Denny Caknan", "Kartonyono Medot Janji"), ("Denny Caknan", "Los Dol"),
    ("Denny Caknan", "Sugeng Dalu"), ("Denny Caknan", "Sampek Tuwek"), ("Denny Caknan", "Kalih Welasku"),
    ("Denny Caknan", "Sigar"), ("Denny Caknan", "Wirang"), ("Denny Caknan", "Dumes"),
    ("Guyon Waton", "Korban Janji"), ("Guyon Waton", "Perlahan"), ("Guyon Waton", "Sebatas Patok Tenda"),
    ("Guyon Waton", "Pelanggaran"), ("Guyon Waton", "Sanes"), ("Happy Asmara", "Rungkad"),
    ("Happy Asmara", "Kelebus"), ("Gilga Sahid", "Nemen"), ("Gilga Sahid", "Ginio"), ("Gilga Sahid", "Alum"),
    ("NDX AKA", "Nemen"), ("NDX AKA", "Ditinggal Rabi"), ("NDX AKA", "Kelingan Mantan"),
    ("Ndarboy Genk", "Mendung Tanpo Udan"), ("Ndarboy Genk", "Koyo Jogja Istimewa"),
    ("Mahalini", "Sial"), ("Mahalini", "Melawan Restu"), ("Mahalini", "Sisa Rasa"), ("Mahalini", "Kisah Sempurna"),
    ("Mahalini", "Bawa Dia Kembali"), ("Mahalini", "Mati-Matian"), ("Mahalini", "Ini Laguku"),
    ("Tiara Andini", "Usai"), ("Tiara Andini", "Janji Setia"), ("Tiara Andini", "Menjadi Dia"),
    ("Tiara Andini", "Merasa Indah"), ("Tiara Andini", "Kupu-Kupu"), ("Lyodra", "Pesan Terakhir"),
    ("Lyodra", "Sang Dewi"), ("Lyodra", "Dibanding Dia"), ("Lyodra", "Tak Dianggap"),
    ("Ziva Magnolya", "Pilihan yang Terbaik"), ("Ziva Magnolya", "Peri Cintaku"), ("Ziva Magnolya", "Menyesal"),
    ("Tulus", "Hati-Hati di Jalan"), ("Tulus", "Monokrom"), ("Tulus", "Diri"), ("Tulus", "Interaksi"),
    ("Tulus", "Pamit"), ("Tulus", "Sepatu"), ("Tulus", "Gajah"), ("Tulus", "Labirin"),
    ("Yura Yunita", "Tutur Batin"), ("Yura Yunita", "Dunia Tipu-Tipu"), ("Yura Yunita", "Tenang"),
    ("Yura Yunita", "Lihatlah Lebih Dekat"), ("Rizky Febian", "Hingga Tua Bersama"),
    ("Rizky Febian", "Kesempurnaan Cinta"), ("Rizky Febian", "Cuek"), ("Rizky Febian", "Mantra Cinta"),
    ("Rizky Febian", "Makna Cinta"), ("Rizky Febian", "Bermuara"),
    ("Dewa 19", "Kangen"), ("Dewa 19", "Pupus"), ("Dewa 19", "Risalah Hati"), ("Dewa 19", "Separuh Nafas"),
    ("Dewa 19", "Cinta Kan Membawamu Kembali"), ("Dewa 19", "Roman Picisan"), ("Dewa 19", "Kamulah Satu-Satunya"),
    ("Sheila On 7", "Dan"), ("Sheila On 7", "Sephia"), ("Sheila On 7", "Melompat Lebih Tinggi"),
    ("Sheila On 7", "Film Favorit"), ("Sheila On 7", "Mudah Saja"), ("Sheila On 7", "Hari Bersamanya"),
    ("Sheila On 7", "Sebuah Kisah Klasik"), ("Sheila On 7", "Anugerah Terindah Yang Pernah Kumiliki"),
    ("Noah", "Separuh Aku"), ("Noah", "Kisah Cintaku"), ("Noah", "Mungkin Nanti"), ("Noah", "Semua Tentang Kita"),
    ("Noah", "Yang Terdalam"), ("Noah", "Menghapus Jejakmu"), ("Noah", "Bintang Di Surga"), ("Noah", "Cobalah Mengerti"),
    ("Padi", "Semua Tak Sama"), ("Padi", "Kasih Tak Sampai"), ("Padi", "Menanti Sebuah Jawaban"),
    ("Chrisye", "Kala Cinta Menggoda"), ("Chrisye", "Pergilah Kasih"), ("Chrisye", "Pelangi"), ("Chrisye", "Cintaku"),
    ("Glenn Fredly", "Januari"), ("Glenn Fredly", "Sekali Ini Saja"), ("Glenn Fredly", "Kasih Putih"), ("Glenn Fredly", "Sedih Tak Berujung"),
    ("Judika", "Mama Papa Larang"), ("Judika", "Jikalau Kau Cinta"), ("Judika", "Putus Atau Terus"), ("Judika", "Bagaimana Kalau Aku Tidak Baik-Baik Saja"),
    ("Juicy Luicy", "Lantas"), ("Juicy Luicy", "Tanpa Tergesa"), ("Juicy Luicy", "Sayangnya"), ("Juicy Luicy", "Asing"),
    ("Juicy Luicy", "Tampar"), ("Juicy Luicy", "Lampu Kuning"), ("For Revenge", "Serana"), ("For Revenge", "Jakarta Hari Ini"),
    ("For Revenge", "Sadrah"), ("Batas Senja", "Nanti Kita Seperti Ini"), ("Feby Putri", "Runtuh"), ("Feby Putri", "Usik"),
    ("Fiersa Besari", "Celengan Rindu"), ("Fiersa Besari", "Waktu Yang Salah"), ("Fiersa Besari", "April"),
    ("Pamungkas", "To the Bone"), ("Pamungkas", "Kenangan Manis"), ("Pamungkas", "One Only"),
    ("Reality Club", "Anything You Want"), ("Reality Club", "Is It The Answer?"), ("Reality Club", "Am I Bothering You?"),
    ("D'Masiv", "Jangan Menyerah"), ("D'Masiv", "Cinta Ini Membunuhku"), ("Ungu", "Demi Waktu"), ("Ungu", "Kekasih Gelapku"),
    ("Armada", "Asal Kau Bahagia"), ("Armada", "Pergi Pagi Pulang Pagi"), ("Geisha", "Lumpuhkan Ingatanku"),
    ("Kotak", "Pelan-Pelan Saja"), ("Kerispatih", "Tertatih"), ("Kerispatih", "Mengenangmu"),
    ("Vierratale", "Seandainya"), ("Vierratale", "Dengarkan Curhatku"), ("Last Child", "Pedih"), ("Last Child", "Duka"),
    ("Payung Teduh", "Akad"), ("Payung Teduh", "Resah"), ("Fourtwnty", "Zona Nyaman"), ("Fourtwnty", "Fana Merah Jambu"),
    ("Bruno Mars", "Die With A Smile"), ("Bruno Mars", "Just the Way You Are"), ("Bruno Mars", "That's What I Like"),
    ("Lady Gaga", "Die With A Smile"), ("Taylor Swift", "Cruel Summer"), ("Taylor Swift", "Fortnight"),
    ("Taylor Swift", "Anti-Hero"), ("Taylor Swift", "Blank Space"), ("Taylor Swift", "Love Story"),
    ("Billie Eilish", "Birds of a Feather"), ("Billie Eilish", "What Was I Made For?"), ("Billie Eilish", "Bad Guy"),
    ("Sabrina Carpenter", "Espresso"), ("Sabrina Carpenter", "Please Please Please"), ("Sabrina Carpenter", "Taste"),
    ("Olivia Rodrigo", "vampire"), ("Olivia Rodrigo", "drivers license"), ("Olivia Rodrigo", "good 4 u"),
    ("Coldplay", "Yellow"), ("Coldplay", "The Scientist"), ("Coldplay", "Fix You"), ("Coldplay", "Viva La Vida"),
    ("The Weeknd", "Blinding Lights"), ("The Weeknd", "Starboy"), ("The Weeknd", "Save Your Tears"),
    ("Ed Sheeran", "Shape of You"), ("Ed Sheeran", "Perfect"), ("Ed Sheeran", "Photograph"),
    ("Ariana Grande", "we can't be friends"), ("Ariana Grande", "7 rings"), ("Ariana Grande", "positions"),
    ("Dua Lipa", "Levitating"), ("Dua Lipa", "Don't Start Now"), ("Dua Lipa", "Houdini"),
    ("Queen", "Bohemian Rhapsody"), ("Queen", "Love of My Life"), ("Oasis", "Don't Look Back In Anger"),
    ("Oasis", "Wonderwall"), ("Linkin Park", "In the End"), ("Linkin Park", "Numb"),
    ("NewJeans", "Supernatural"), ("NewJeans", "Ditto"), ("NewJeans", "OMG"), ("NewJeans", "Hype Boy"),
    ("BLACKPINK", "How You Like That"), ("BLACKPINK", "Kill This Love"), ("BLACKPINK", "Shut Down"),
    ("BTS", "Dynamite"), ("BTS", "Butter"), ("BTS", "Spring Day"),
    ("YOASOBI", "Idol"), ("YOASOBI", "Yoru ni Kakeru"), ("Fujii Kaze", "Shinunoga E-Wa"), ("Fujii Kaze", "Matsuri"),
    # Additional Indo Pop, Dangdut & Indie Classics
    ("Afgan", "Terima Kasih Cinta"), ("Afgan", "Bukan Cinta Biasa"), ("Afgan", "Jodoh Pasti Bertemu"),
    ("Afgan", "Sadis"), ("Afgan", "Panah Asmara"), ("Afgan", "Lenggang Puspita"),
    ("Rossa", "Hati Yang Kau Sakiti"), ("Rossa", "Tegar"), ("Rossa", "Ayat Ayat Cinta"),
    ("Rossa", "Pudar"), ("Rossa", "Kini"), ("Rossa", "Jangan Hilangkan Dia"),
    ("Ungu", "Kekasih Gelapku"), ("Ungu", "Demi Waktu"), ("Ungu", "Tercipta Untukku"),
    ("Ungu", "Cinta Dalam Hati"), ("Ungu", "Hampa Hatiku"), ("Ungu", "Andai Ku Tahu"),
    ("Slank", "Ku Tak Bisa"), ("Slank", "Terlalu Manis"), ("Slank", "Virus"),
    ("Slank", "I Miss You But I Hate You"), ("Slank", "Balikin"),
    ("Iwan Fals", "Bento"), ("Iwan Fals", "Bongkar"), ("Iwan Fals", "Surat Buat Wakil Rakyat"),
    ("Iwan Fals", "Ibu"), ("Iwan Fals", "Yang Terlupakan"), ("Iwan Fals", "Ijinkan Aku Menyayangimu"),
    ("Kangen Band", "Yolanda"), ("Kangen Band", "Tentang Aku Kau Dan Dia"), ("Kangen Band", "Pujaan Hati"),
    ("Kangen Band", "Doy"), ("Kangen Band", "Cinta Sampai Mati"),
    ("ST12", "Saat Terakhir"), ("ST12", "Jangan Pernah Berubah"), ("ST12", "Puspa"),
    ("ST12", "Rasa Yang Tertinggal"), ("ST12", "Cari Pacar Lagi"),
    ("Wali", "Baik Baik Sayang"), ("Wali", "Ada Gajah Di Balik Batu"), ("Wali", "Yank"),
    ("Wali", "Si Udin Bertanya"), ("Wali", "Doaku Untukmu Sayang"),
    ("Armada", "Harusnya Aku"), ("Armada", "Buka Hatimu"), ("Armada", "Awas Jatuh Cinta"),
    ("D'Masiv", "Merindukanmu"), ("D'Masiv", "Diam Tanpa Kata"), ("D'Masiv", "Rindu Setengah Mati"),
    ("Kerispatih", "Bila Rasaku Ini Rasamu"), ("Kerispatih", "Kejujuran Hati"), ("Kerispatih", "Demi Cinta"),
    ("Ada Band", "Karena Wanita Ingin Dimengerti"), ("Ada Band", "Manusia Bodoh"), ("Ada Band", "Haruskah Ku Mati"),
    ("Samsons", "Kenangan Terindah"), ("Samsons", "Naluri Lelaki"), ("Samsons", "Kisah Tak Sempurna"),
    ("Geisha", "Jika Cinta Dia"), ("Geisha", "Cobalah Mengerti"),
    ("Kotak", "Beraksi"), ("Kotak", "Terbang"),
    ("Cakra Khan", "Kekasih Bayangan"), ("Cakra Khan", "Harus Terpisah"), ("Cakra Khan", "Mencari Cinta Sejati"),
    ("Bunga Citra Lestari", "Cinta Sejati"), ("Bunga Citra Lestari", "Kecewa"), ("Bunga Citra Lestari", "Karena Kucinta Kau"),
    ("Bunga Citra Lestari", "Sunny"), ("Bunga Citra Lestari", "Aku Dan Dirimu"),
    ("Raisa", "Kali Kedua"), ("Raisa", "Serba Salah"), ("Raisa", "Mantan Terindah"),
    ("Raisa", "Jatuh Hati"), ("Raisa", "Could It Be"), ("Raisa", "Biarkanlah"),
    ("Isyana Sarasvati", "Tetap Dalam Jiwa"), ("Isyana Sarasvati", "Kau Adalah"), ("Isyana Sarasvati", "Mimpi"),
    ("Maudy Ayunda", "Perahu Kertas"), ("Maudy Ayunda", "Untuk Apa"), ("Maudy Ayunda", "Tiba-Tiba Cinta Datang"),
    ("Ardhito Pramono", "Bitterlove"), ("Ardhito Pramono", "Here We Go Again / Fanfare"), ("Ardhito Pramono", "Fine Today"),
    ("Idgitaf", "Takut"), ("Idgitaf", "Satu-Satu"), ("Idgitaf", "Dermaga"),
    ("Dere", "Kota"), ("Dere", "Tanya"), ("Dere", "Berisik"),
    ("Daun Jatuh", "Resah Jadi Luka"), ("Daun Jatuh", "Momen"),
    ("Soegi Bornean", "Asmalibrasi"), ("Soegi Bornean", "Bait Perindu"),
    ("Keisya Levronka", "Tak Ingin Usai"), ("Keisya Levronka", "Hidup Tanpamu"),
    ("Anggi Marito", "Tak Segampang Itu"), ("Anggi Marito", "Kisah Yang Salah"),
    ("Fabio Asher", "Bertahan Terluka"), ("Fabio Asher", "Rumah Singgah"), ("Fabio Asher", "Akhir Bentuk Cinta"),
    ("Raim Laode", "Komang"), ("Raim Laode", "Lesung Pipi"),
    ("Didi Kempot", "Pamer Bojo"), ("Didi Kempot", "Banyu Langit"), ("Didi Kempot", "Stasiun Balapan"),
    ("Didi Kempot", "Layang Kangen"), ("Didi Kempot", "Suket Teki"),
    # Additional Global Pop, K-Pop & J-Pop
    ("Adele", "Someone Like You"), ("Adele", "Rolling in the Deep"), ("Adele", "Easy On Me"),
    ("Adele", "Hello"), ("Adele", "Set Fire to the Rain"), ("Adele", "When We Were Young"),
    ("Sam Smith", "Stay With Me"), ("Sam Smith", "I'm Not The Only One"), ("Sam Smith", "Unholy"),
    ("Sam Smith", "Too Good At Goodbyes"),
    ("Harry Styles", "As It Was"), ("Harry Styles", "Watermelon Sugar"), ("Harry Styles", "Sign of the Times"),
    ("Shawn Mendes", "Senorita"), ("Shawn Mendes", "Treat You Better"), ("Shawn Mendes", "Stitches"),
    ("Charlie Puth", "Attention"), ("Charlie Puth", "We Don't Talk Anymore"), ("Charlie Puth", "See You Again"),
    ("Charlie Puth", "Left and Right"),
    ("Justin Bieber", "Ghost"), ("Justin Bieber", "Peaches"), ("Justin Bieber", "Love Yourself"),
    ("Justin Bieber", "Sorry"), ("Justin Bieber", "Stay"),
    ("Post Malone", "Circles"), ("Post Malone", "Sunflower"), ("Post Malone", "Rockstar"),
    ("Post Malone", "Congratulations"), ("Post Malone", "I Had Some Help"),
    ("Drake", "God's Plan"), ("Drake", "One Dance"), ("Drake", "Hotline Bling"),
    ("Kendrick Lamar", "Not Like Us"), ("Kendrick Lamar", "HUMBLE."), ("Kendrick Lamar", "All The Stars"),
    ("SZA", "Kill Bill"), ("SZA", "Snooze"), ("SZA", "Good Days"),
    ("Rihanna", "Diamonds"), ("Rihanna", "Umbrella"), ("Rihanna", "We Found Love"),
    ("Katy Perry", "Roar"), ("Katy Perry", "Firework"), ("Katy Perry", "Dark Horse"),
    ("Maroon 5", "Sugar"), ("Maroon 5", "Girls Like You"), ("Maroon 5", "Memories"),
    ("Maroon 5", "Payphone"), ("Maroon 5", "She Will Be Loved"),
    ("Imagine Dragons", "Believer"), ("Imagine Dragons", "Demons"), ("Imagine Dragons", "Radioactive"),
    ("Imagine Dragons", "Bones"), ("Imagine Dragons", "Thunder"),
    ("OneRepublic", "Counting Stars"), ("OneRepublic", "I Ain't Worried"), ("OneRepublic", "Secrets"),
    ("Eminem", "Houdini"), ("Eminem", "Lose Yourself"), ("Eminem", "Without Me"),
    ("TWICE", "What is Love?"), ("TWICE", "FANCY"), ("TWICE", "Feel Special"),
    ("TWICE", "The Feels"), ("TWICE", "Talk that Talk"),
    ("Stray Kids", "Chk Chk Boom"), ("Stray Kids", "God's Menu"), ("Stray Kids", "Maniac"),
    ("SEVENTEEN", "Super"), ("SEVENTEEN", "HOT"), ("SEVENTEEN", "MAESTRO"),
    ("IVE", "LOVE DIVE"), ("IVE", "After LIKE"), ("IVE", "I AM"), ("IVE", "HEYA"),
    ("aespa", "Supernova"), ("aespa", "Armageddon"), ("aespa", "Next Level"), ("aespa", "Spicy"),
    ("LE SSERAFIM", "EASY"), ("LE SSERAFIM", "Smart"), ("LE SSERAFIM", "ANTIFRAGILE"), ("LE SSERAFIM", "Perfect Night"),
    ("IU", "Celebrity"), ("IU", "Love wins all"), ("IU", "eight"), ("IU", "Blueming"),
    ("Taeyeon", "To. X"), ("Taeyeon", "INVU"), ("Taeyeon", "Four Seasons"),
    ("Kenshi Yonezu", "Lemon"), ("Kenshi Yonezu", "Kick Back"), ("Kenshi Yonezu", "Shinigami"),
    ("Ado", "Show"), ("Ado", "Usseewa"), ("Ado", "Odo"), ("Ado", "Kura Kura"),
    ("Eve", "Kaikai Kitan"), ("Eve", "Dramaturgy"),
    ("King Gnu", "SPECIALZ"), ("King Gnu", "Hakujitsu"),
    ("RADWIMPS", "Sparkle"), ("RADWIMPS", "Zenzenzense"), ("RADWIMPS", "Nandemonaiya"),
    ("Official HIGE DANdism", "Pretender"), ("Official HIGE DANdism", "Cry Baby"), ("Official HIGE DANdism", "Subtitle"),
    ("Aimyon", "Marigold"), ("Aimyon", "Harunohi"),
    ("Yuuri", "Dry Flower"), ("Yuuri", "Betelgeuse"),
    ("LiSA", "Gurenge"), ("LiSA", "Homura"),
    ("Kana-Boon", "Silhouette"), ("Ikimonogakari", "Blue Bird"),
    # Part 2 Classics
    # Indo Pop & Band Legends
    ("Gigi", "11 Januari"), ("Gigi", "Nakal"), ("Gigi", "Terbang"), ("Gigi", "Pintu Sorga"), ("Gigi", "Andai"),
    ("Padi", "Sobat"), ("Padi", "Mahadewi"), ("Padi", "Sesuatu Yang Indah"), ("Padi", "Begitu Indah"), ("Padi", "Tempat Terakhir"),
    ("Naif", "Buta Hati"), ("Naif", "Piknik 72"), ("Naif", "Karena Kamu Cuma Satu"), ("Naif", "Mobil Balap"), ("Naif", "Benci Untuk Mencinta"),
    ("Sheila On 7", "J.A.P"), ("Sheila On 7", "Kita"), ("Sheila On 7", "Pria Kesepian"), ("Sheila On 7", "Sahabat Sejati"), ("Sheila On 7", "Pejantan Tangguh"),
    ("Dewa 19", "Kirana"), ("Dewa 19", "Cukup Siti Nurbaya"), ("Dewa 19", "Aku Milikmu"), ("Dewa 19", "Elang"), ("Dewa 19", "Satu"),
    ("Noah", "Ada Apa Denganmu"), ("Noah", "Di Atas Normal"), ("Noah", "Kukatakan Dengan Indah"), ("Noah", "Khayalan Tingkat Tinggi"), ("Noah", "Menunggumu"),
    ("Nidji", "Laskar Pelangi"), ("Nidji", "Hapus Aku"), ("Nidji", "Biarlah"), ("Nidji", "Arti Sahabat"),
    ("Letto", "Ruang Rindu"), ("Letto", "Sandaran Hati"), ("Letto", "Sebelum Cahaya"), ("Letto", "Permintaan Hati"),
    ("Maliq & D'Essentials", "Kita Bikin Romantis"), ("Maliq & D'Essentials", "Adu Rayu"), ("Maliq & D'Essentials", "Untitled"), ("Maliq & D'Essentials", "Pilihanku"), ("Maliq & D'Essentials", "Himalaya"),
    ("Kahitna", "Cantik"), ("Kahitna", "Soulmate"), ("Kahitna", "Andai Dia Tahu"), ("Kahitna", "Mantan Terindah"), ("Kahitna", "Untukku"),
    ("Yovie & Nuno", "Menjaga Hati"), ("Yovie & Nuno", "Janji Suci"), ("Yovie & Nuno", "Merindu Lagi"), ("Yovie & Nuno", "Dia Milikku"),
    ("Reza Artamevia", "Keabadian"), ("Reza Artamevia", "Pertama"), ("Reza Artamevia", "Berharap Tak Berpisah"),
    ("Krisdayanti", "Menghitung Hari"), ("Krisdayanti", "Cobalah Untuk Setia"), ("Krisdayanti", "Mencintaimu"),
    ("Ebiet G. Ade", "Berita Kepada Kawan"), ("Ebiet G. Ade", "Titip Rindu Buat Ayah"), ("Ebiet G. Ade", "Untuk Kita Renungkan"),
    ("Chrisye", "Badai Pasti Berlalu"), ("Chrisye", "Lilin-Lilin Kecil"), ("Chrisye", "Seperti Yang Kau Minta"), ("Chrisye", "Aku Cinta Dia"),
    ("Vina Panduwinata", "Burung Camar"), ("Vina Panduwinata", "Surat Cinta"),
    ("Shaggydog", "Di Sayidan"), ("Shaggydog", "Kembali Berdansa"),
    ("Superman Is Dead", "Jadilah Legenda"), ("Superman Is Dead", "Sunset Di Tanah Anarki"), ("Superman Is Dead", "Kuat Kita Bersinar"),
    ("Pee Wee Gaskins", "Dari Mata Sang Garuda"), ("Pee Wee Gaskins", "Sebuah Rahasia"),
    # Global Pop, Rock, EDM & Evergreen
    ("Michael Jackson", "Billie Jean"), ("Michael Jackson", "Beat It"), ("Michael Jackson", "Thriller"), ("Michael Jackson", "Smooth Criminal"), ("Michael Jackson", "Man in the Mirror"),
    ("Queen", "We Will Rock You"), ("Queen", "We Are the Champions"), ("Queen", "Don't Stop Me Now"), ("Queen", "Another One Bites the Dust"),
    ("The Beatles", "Hey Jude"), ("The Beatles", "Let It Be"), ("The Beatles", "Yesterday"), ("The Beatles", "Here Comes the Sun"),
    ("Elton John", "Rocket Man"), ("Elton John", "Your Song"), ("Elton John", "Can You Feel the Love Tonight"),
    ("Bon Jovi", "It's My Life"), ("Bon Jovi", "Livin' On A Prayer"), ("Bon Jovi", "Always"),
    ("Guns N' Roses", "Sweet Child O' Mine"), ("Guns N' Roses", "November Rain"), ("Guns N' Roses", "Don't Cry"),
    ("Metallica", "Enter Sandman"), ("Metallica", "Nothing Else Matters"), ("Metallica", "Master of Puppets"),
    ("AC/DC", "Back In Black"), ("AC/DC", "Highway to Hell"), ("AC/DC", "Thunderstruck"),
    ("Nirvana", "Smells Like Teen Spirit"), ("Nirvana", "Come As You Are"), ("Nirvana", "Lithium"),
    ("Green Day", "Boulevard of Broken Dreams"), ("Green Day", "21 Guns"), ("Green Day", "American Idiot"), ("Green Day", "Wake Me Up When September Ends"),
    ("Red Hot Chili Peppers", "Californication"), ("Red Hot Chili Peppers", "Under the Bridge"), ("Red Hot Chili Peppers", "Can't Stop"),
    ("Blink-182", "All The Small Things"), ("Blink-182", "I Miss You"),
    ("My Chemical Romance", "Welcome to the Black Parade"), ("My Chemical Romance", "Helena"),
    ("Fall Out Boy", "Centuries"), ("Fall Out Boy", "Sugar, We're Goin Down"),
    ("Panic! At The Disco", "High Hopes"), ("Panic! At The Disco", "I Write Sins Not Tragedies"),
    ("twenty one pilots", "Stressed Out"), ("twenty one pilots", "Ride"), ("twenty one pilots", "Heathens"),
    ("Sia", "Chandelier"), ("Sia", "Cheap Thrills"), ("Sia", "Unstoppable"),
    ("Lana Del Rey", "Summertime Sadness"), ("Lana Del Rey", "Video Games"), ("Lana Del Rey", "Young and Beautiful"),
    ("Lady Gaga", "Bad Romance"), ("Lady Gaga", "Poker Face"), ("Lady Gaga", "Shallow"), ("Lady Gaga", "Always Remember Us This Way"), ("Lady Gaga", "Judas"),
    ("Beyoncé", "Halo"), ("Beyoncé", "Single Ladies"), ("Beyoncé", "Crazy In Love"), ("Beyoncé", "TEXAS HOLD 'EM"),
    ("Shakira", "Hips Don't Lie"), ("Shakira", "Waka Waka"),
    ("Pitbull", "Timber"), ("Pitbull", "Give Me Everything"),
    ("Avicii", "Wake Me Up"), ("Avicii", "The Nights"), ("Avicii", "Waiting For Love"), ("Avicii", "Levels"),
    ("Alan Walker", "Faded"), ("Alan Walker", "Alone"), ("Alan Walker", "The Spectre"), ("Alan Walker", "On My Way"),
    ("Marshmello", "Happier"), ("Marshmello", "Alone"), ("Marshmello", "Silence"),
    ("The Chainsmokers", "Closer"), ("The Chainsmokers", "Something Just Like This"), ("The Chainsmokers", "Don't Let Me Down"),
    ("DJ Snake", "Let Me Love You"), ("DJ Snake", "Taki Taki"), ("DJ Snake", "Middle"),
    ("Martin Garrix", "Animals"), ("Martin Garrix", "Scared to Be Lonely"), ("Martin Garrix", "In the Name of Love"),
    ("Zedd", "Clarity"), ("Zedd", "Stay"), ("Zedd", "The Middle"),
    ("Clean Bandit", "Rather Be"), ("Clean Bandit", "Symphony"), ("Clean Bandit", "Rockabye"),
    ("Jason Mraz", "I'm Yours"), ("Jason Mraz", "I Won't Give Up"), ("Jason Mraz", "Lucky"),
    ("John Legend", "All of Me"), ("John Legend", "Ordinary People"),
    ("James Arthur", "Say You Won't Let Go"), ("James Arthur", "Impossible"),
    ("Lewis Capaldi", "Someone You Loved"), ("Lewis Capaldi", "Before You Go"),
    ("Calum Scott", "You Are The Reason"), ("Calum Scott", "Dancing On My Own"),
    ("Dean Lewis", "Be Alright"), ("Dean Lewis", "How Do I Say Goodbye"),
    ("Vance Joy", "Riptide"), ("Passenger", "Let Her Go"), ("Tom Odell", "Another Love"),
    # K-Pop
    ("BIGBANG", "BANG BANG BANG"), ("BIGBANG", "Fantastic Baby"), ("BIGBANG", "Haru Haru"), ("BIGBANG", "Loser"),
    ("2NE1", "I AM THE BEST"), ("2NE1", "Come Back Home"), ("2NE1", "Lonely"),
    ("EXO", "Growl"), ("EXO", "Love Shot"), ("EXO", "Monster"), ("EXO", "Call Me Baby"),
    ("Red Velvet", "Psycho"), ("Red Velvet", "Bad Boy"), ("Red Velvet", "Red Flavor"), ("Red Velvet", "Russian Roulette"),
    ("NCT 127", "Kick It"), ("NCT 127", "Cherry Bomb"),
    ("NCT DREAM", "Candy"), ("NCT DREAM", "Glitch Mode"), ("NCT DREAM", "ISTJ"),
    ("TXT", "Sugar Rush Ride"), ("TXT", "Good Boy Gone Bad"), ("TXT", "Blue Hour"),
    ("ENHYPEN", "Bite Me"), ("ENHYPEN", "Drunk-Dazed"), ("ENHYPEN", "FEVER"),
    ("ITZY", "WANNABE"), ("ITZY", "DALLA DALLA"), ("ITZY", "LOCO"),
    ("STAYC", "ASAP"), ("STAYC", "Stereotype"), ("STAYC", "RUN2U"),
    ("NMIXX", "Dash"), ("NMIXX", "Love Me Like This"),
    ("BABYMONSTER", "SHEESH"), ("BABYMONSTER", "BATTER UP"),
    ("ILLIT", "Magnetic"), ("ILLIT", "Lucky Girl Syndrome"),
    ("KISS OF LIFE", "Sticky"), ("KISS OF LIFE", "Midas Touch"),
    ("(G)I-DLE", "Queencard"), ("(G)I-DLE", "TOMBOY"), ("(G)I-DLE", "Fate"), ("(G)I-DLE", "Super Lady"), ("(G)I-DLE", "Nxde"),
    ("AKMU", "Love Lee"), ("AKMU", "How can I love the heartbreak, it's you I love"), ("AKMU", "200%"),
    ("BOL4", "Some"), ("BOL4", "To My Youth"), ("BOL4", "Galaxy"),
    ("MeloMance", "Gift"), ("MeloMance", "Love Maybe"),
    ("Paul Kim", "Every day Every Moment"), ("Paul Kim", "Me After You"),
    # J-Pop & Anime
    ("Aimer", "Zankyosanka"), ("Aimer", "Kataomoi"), ("Aimer", "Brave Shine"),
    ("TK from Ling tosite sigure", "Unravel"),
    ("KANA-BOON", "Baton Road"), ("KANA-BOON", "Spiral"),
    ("ASIAN KUNG-FU GENERATION", "Haruka Kanata"), ("ASIAN KUNG-FU GENERATION", "Rewrite"), ("ASIAN KUNG-FU GENERATION", "Re:Re:"),
    ("FLOW", "GO!!!"), ("FLOW", "Sign"), ("FLOW", "Colors"),
    ("SPYAIR", "Imagination"), ("SPYAIR", "Samurai Heart"), ("SPYAIR", "Orange"),
    ("Burnout Syndromes", "Fly High!!"), ("Burnout Syndromes", "Hikariare"),
    ("Goose house", "Hikaru Nara"),
    ("Sukima Switch", "Kanade"),
    ("Utada Hikaru", "First Love"), ("Utada Hikaru", "One Last Kiss"),
    ("YUI", "Tokyo"), ("YUI", "Goodbye Days"), ("YUI", "Rolling Star"),
    ("Mika Nakashima", "Yuki no Hana"), ("Mika Nakashima", "Glamorous Sky"),
    ("Official HIGE DANdism", "I LOVE..."), ("Official HIGE DANdism", "Mixed Nuts"), ("Official HIGE DANdism", "White Noise"),
    ("Mrs. GREEN APPLE", "Dance Hall"), ("Mrs. GREEN APPLE", "Ao to Natsu"), ("Mrs. GREEN APPLE", "Inferno"), ("Mrs. GREEN APPLE", "Que Sera Sera"), ("Mrs. GREEN APPLE", "Lilac"),
    ("Vaundy", "Odoriko"), ("Vaundy", "Kaijuu no Hanauta"), ("Vaundy", "Chainsaw Blood"),
    ("back number", "Takane no Hanako-san"), ("back number", "Happy End"), ("back number", "Christmas Song"),
    ("DISH//", "Neko"),
    ("Creepy Nuts", "Bling-Bang-Bang-Born"), ("Creepy Nuts", "Otonoke")
]

KWORB_URLS = [
    'https://kworb.net/spotify/country/id_daily.html',
    'https://kworb.net/spotify/country/id_weekly.html',
    'https://kworb.net/spotify/country/global_daily.html',
    'https://kworb.net/spotify/country/global_weekly.html',
    'https://kworb.net/spotify/country/us_daily.html',
    'https://kworb.net/spotify/country/gb_daily.html',
    'https://kworb.net/spotify/country/jp_daily.html',
    'https://kworb.net/spotify/country/kr_daily.html',
    'https://kworb.net/spotify/country/my_daily.html',
    'https://kworb.net/spotify/country/ph_daily.html',
    'https://kworb.net/spotify/country/sg_daily.html',
    'https://kworb.net/spotify/country/th_daily.html',
    'https://kworb.net/spotify/country/br_daily.html',
    'https://kworb.net/spotify/country/mx_daily.html',
    'https://kworb.net/spotify/country/de_daily.html',
    'https://kworb.net/spotify/country/fr_daily.html',
    'https://kworb.net/spotify/country/es_daily.html',
    'https://kworb.net/spotify/country/it_daily.html',
    'https://kworb.net/spotify/country/au_daily.html',
    'https://kworb.net/spotify/country/ca_daily.html',
]

def clean_text(s):
    if not s:
        return ""
    s = re.sub(r'\(.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\[.*?(?:feat|ft\.|official|video|audio|remix|version|deluxe|bonus).*?\]', '', s, flags=re.IGNORECASE)
    return s.strip()

def fetch_chart_tracks():
    tracks = set()
    for artist, title in INDO_ESSENTIALS:
        tracks.add((artist.strip(), title.strip()))

    pattern = re.compile(r'<td class="text mp"><div><a href="\.\./artist/[^"]+">([^<]+)</a>\s*-\s*<a href="\.\./track/[^"]+">([^<]+)</a>')
    for u in KWORB_URLS:
        try:
            req = urllib.request.Request(u, headers=HEADERS)
            html = urllib.request.urlopen(req, timeout=6).read().decode('utf-8', errors='ignore')
            matches = pattern.findall(html)
            for artist, title in matches:
                tracks.add((artist.strip(), title.strip()))
        except Exception:
            pass
    return list(tracks)

def search_lrclib(artist, title):
    q = urllib.parse.quote(f"{clean_text(title)} {clean_text(artist)}")
    url = f"https://lrclib.net/api/search?q={q}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if not isinstance(data, list):
                return None
            for item in data:
                if item.get("syncedLyrics"):
                    return item
            if data:
                return data[0]
    except Exception:
        pass
    return None

def resolve_youtube_videoids(artist, title):
    url = 'https://www.youtube.com/youtubei/v1/search?prettyPrint=false'
    query = f"{artist} - {title}"
    payload = {
        'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20240101.01.00'}},
        'query': query
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    vids = []
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            resp = json.loads(r.read().decode('utf-8'))
            sections = resp.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
            for sec in sections:
                items = sec.get('itemSectionRenderer', {}).get('contents', [])
                for it in items:
                    vr = it.get('videoRenderer')
                    if vr and 'videoId' in vr:
                        vids.append(vr['videoId'])
                        if len(vids) >= 2:
                            break
                if len(vids) >= 2:
                    break
    except Exception:
        pass
    return vids

def write_lyric_file(vid, lrc_obj, fallback_title, fallback_artist):
    song_title = lrc_obj.get("trackName") or fallback_title
    artist_name = lrc_obj.get("artistName") or fallback_artist
    album_name = lrc_obj.get("albumName") or ""
    duration = int(lrc_obj.get("duration") or 0)
    plain_lyrics = lrc_obj.get("plainLyrics") or ""
    synced_lyrics = lrc_obj.get("syncedLyrics") or ""

    payload = {
        "success": True,
        "error": None,
        "data": [
            {
                "id": vid,
                "videoId": vid,
                "songTitle": song_title,
                "artistName": artist_name,
                "albumName": album_name,
                "durationSeconds": duration,
                "plainLyric": plain_lyrics,
                "syncedLyrics": synced_lyrics,
                "richSyncLyrics": None,
                "trackType": None,
                "vote": 100,
                "contributor": "LRCLIB / HiFi Community",
                "contributorEmail": "lyrics@hifi.org"
            }
        ]
    }
    filepath = os.path.join(LYRICS_DIR, f"{vid}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def process_track(track):
    artist, title = track
    lrc = search_lrclib(artist, title)
    if not lrc:
        return 0
    vids = resolve_youtube_videoids(artist, title)
    if not vids:
        return 0
    saved = 0
    for vid in vids:
        filepath = os.path.join(LYRICS_DIR, f"{vid}.json")
        # Overwrite or update with latest
        write_lyric_file(vid, lrc, title, artist)
        saved += 1
    return saved

def update_index():
    lyrics_files = [f for f in os.listdir(LYRICS_DIR) if f.endswith(".json") and len(f) == 16]
    index_data = {
        "service": "HiFi Lyrics Repository",
        "version": "2.0.0",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_tracks": len(lyrics_files),
        "status": "online"
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    return len(lyrics_files)

def main():
    print("Step 1: Gathering chart and seed tracks...")
    all_tracks = fetch_chart_tracks()
    print(f"Total track candidates: {len(all_tracks)}")

    print("Step 2: Harvesting lyrics from LRCLIB & mapping YouTube video IDs...")
    total_saved = 0
    completed = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(process_track, t): t for t in all_tracks}
        for future in as_completed(futures):
            completed += 1
            try:
                saved = future.result()
                total_saved += saved
            except Exception:
                pass
            if completed % 50 == 0 or completed == len(all_tracks):
                elapsed = time.time() - start_time
                print(f"Progress: {completed}/{len(all_tracks)} tracks processed. Saved: {total_saved}. ({elapsed:.1f}s)")

    print("Step 3: Building catalog index...")
    total_files = update_index()
    print(f"DONE! Total lyrics in database: {total_files} files.")

if __name__ == "__main__":
    main()
