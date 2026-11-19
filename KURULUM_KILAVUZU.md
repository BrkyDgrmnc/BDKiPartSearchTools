# BDKiPartSearchTools — Kurulum ve Kullanım Kılavuzu

**BDKiPartSearchTools** (*by Berkay Değirmenci*), KiCad 8, 9 ve 10 sürümleri için geliştirilmiş; **LCSC (EasyEDA)** ve **DigiKey** üzerinden komponent arama, **Şematik Sembol (`.kicad_sym`)**, **PCB Footprint (`.kicad_mod`)** ve **3D Model (`.step` / `.wrl`)** indirme ve **Canlı Fiyat/Stok Destekli Akıllı Mühendislik BOM** oluşturma eklentisidir.

---

## 1. Kurulum Yöntemleri

Eklentiyi iki farklı yöntemle kurabilirsiniz:

### Yöntem A: KiCad Eklenti ve İçerik Yöneticisi (PCM) ile Resmî Kurulum *(Önerilen)*

1. Eğer `.zip` paketi henüz oluşturulmadıysa (veya kodda değişiklik yaptıysanız), aşağıdaki komutla güncel PCM paketini oluşturun:
   ```powershell
   & "E:\KiCad\bin\python.exe" "e:\Development\Kicad\kicad-lcsc-digikey-plugin\build_pcm_package.py"
   ```
   *(Not: KiCad standart dizinde kuruluysa `"C:\Program Files\KiCad\10.0\bin\python.exe"` yolunu kullanabilirsiniz).*
2. **KiCad 10** ana penceresini (Proje Yöneticisi) açın.
3. **`Eklenti ve İçerik Yöneticisi` (Plugin and Content Manager)** butonuna tıklayın.
4. Sol alt köşedeki **`Dosyadan Kur...` (Install from File...)** butonuna tıklayın.
5. `dist` klasörü içindeki şu dosyayı seçin:
   ```text
   e:\Development\Kicad\kicad-lcsc-digikey-plugin\dist\com.berkaydegirmenci.bdkipartsearchtools-1.0.0-pcm.zip
   ```
6. Sağ alt köşedeki **`Bekleyen Değişiklikleri Uygula` (Apply Pending Changes)** butonuna tıklayın.

---

### Yöntem B: Otomatik Geliştirici Kurulum Betiği ile Tek Komutta Kurulum

Tek bir komutla hem PCM paketini oluşturmak, hem eklentiyi KiCad 10 dizinine kopyalamak, hem de **14 kategori kütüphanesini (`ARI_Resistors`, `ARI_Capacitors`, `ARI_ICs_MCUs` vb.)** KiCad'in `sym-lib-table` ve `fp-lib-table` tablolarına otomatik kaydetmek için:

```powershell
& "E:\KiCad\bin\python.exe" "e:\Development\Kicad\kicad-lcsc-digikey-plugin\install_to_kicad10.py"
```

> **Önemli Not:** İlk kurulumdan sonra yeni oluşturulan 14 kategori kütüphanesinin (`ARI_*`) KiCad tarafından belleğe alınması için **KiCad'i (veya açık olan Şematik / PCB Editörünü) bir kez kapatıp yeniden açın.**

---

## 2. Eklentiye Erişim (Nereden Açılır?)

### A) Şematik Editörü (Eeschema) İçinden:
1. **Üst Araç Çubuğu (`BD / PS` İkonu):**
   * Şematik Editörü üst araç çubuğunun sağ tarafındaki **`BD / PS` (`BDKiPartSearchTools`)** butonuna tıklayın.
   * *(İkon görünmüyorsa `Tercihler -> Tercihler -> Eklentiler (Plugins)` menüsünden `BDKiPartSearchTools` yanında "Araç çubuğunda göster" seçeneğinin işaretli olduğunu kontrol edin).*
2. **BOM (Malzeme Listesi) Aracı Üzerinden:**
   * Şematik Editörü üst araç çubuğundaki **`BOM` (Malzeme Listesi Oluştur)** ikonuna tıklayın.
   * Listede **`BDKiPartSearchTools`** seçili haldeyken **`Oluştur (Generate)`** butonuna basın.

### B) PCB Editörü (Pcbnew) İçinden:
* Üst araç çubuğundaki **`BD / PS` (`BDKiPartSearchTools`)** butonuna veya `Araçlar -> Harici Eklentiler -> BDKiPartSearchTools` menüsüne tıklayın.

### C) Bağımsız Pencere (Standalone) Olarak:
KiCad'i hiç açmadan doğrudan masaüstünden veya terminalden çalıştırmak için:
```powershell
& "E:\KiCad\bin\python.exe" "e:\Development\Kicad\kicad-lcsc-digikey-plugin\run_standalone.py"
```

---

## 3. Kullanım Adımları

### 🔍 1. Sekme: Komponent Ara ve Kütüphaneye Ekle
1. **Arama:** Arama kutusuna üretici parça kodu (`STM32F103C8T6`, `RP2040`, `PESD2CAN`), LCSC parça numarası (`C8734`, `C2040`) veya değer/paket (`10k 0402`, `100nF 0603`) yazıp **Enter** tuşuna veya **`🔍 Ara`** butonuna basın. Yeni arama yapmak için **`✖ Temizle`** butonunu kullanabilirsiniz.
2. **Canlı 2D Önizleme:** Sonuç listesinden bir parçaya tıkladığınızda sol altta **Şematik Sembolü** ve **PCB Footprint**'in canlı 2D çizimi ile **`3D STEP: Hazır ✓`** durumu görüntülenir.
3. **Kategori ve Parametre Kontrolü:** Sağ altta komponentin ekleneceği **Kategori** (`Resistors`, `Capacitors`, `ICs_MCUs`, `Diodes_Protection` vb.), `Sembol Adı`, `Ref Prefix`, `Footprint Adı`, `LCSC Parça No`, `DigiKey Parça No` ve `Birim Fiyat ($)` alanları otomatik dolar; dilerseniz içe aktarmadan önce düzenleyebilirsiniz.
4. **İçe Aktarma:** **`📥 KiCad Kütüphanesine İçe Aktar`** butonuna tıkladığınızda:
   * Şematik sembolü ilgili kategori dosyasına (örn. `ARI_ICs_MCUs.kicad_sym`) tüm BOM özellikleriyle (`MPN`, `Manufacturer`, `LCSC_Part`, `DigiKey_Part`, `Unit_Price`, `Stock`, `Datasheet`, `Supplier_URL`) birlikte eklenir.
   * Footprint dosyası (`.kicad_mod`) ilgili `.pretty` klasörüne kaydedilir.
   * 3D model (`.step` ve seçiliyse `.wrl`) `.3dshapes` klasörüne indirilir ve footprint içine eksen/ofset koordinatlarıyla otomatik bağlanır.
5. **Şematiğe Yerleştirme:** Şematik Editörüne (`Eeschema`) geçip klavyeden **`A`** (*Sembol Ekle*) tuşuna basın ve parça adını aratarak doğrudan şematiğinize yerleştirin. *(Eğer o kategorideki ilk parçayı Eeschema açıkken eklediyseniz `Tercihler -> Sembol Kütüphanelerini Yönet -> Tamam` diyerek veya Eeschema'yı yeniden başlatarak kütüphane önbelleğini yenileyebilirsiniz).*

---

### 📊 2. Sekme: Akıllı BOM, Fiyat ve Stok Çıktısı
1. **`🔄 Aktif Projeden Yükle (Şematik + PCB)`** butonuna tıklayın (veya **`📂 Proje Klasörü Seç...`** ile istediğiniz proje klasörünü seçin).
2. **`Üretilecek Kart Adedi (PCB Sayısı)`** değerini girin (örn. `1`, `10`, `100`). Toplam sipariş adedine göre kademeli birim fiyatlar (`1+`, `10+`, `100+`, `1000+`) otomatik hesaplanır.
3. **`⚡ Canlı Fiyat, Stok ve Parça Numaralarını Çek (LCSC / DigiKey)`** butonuna basarak listedeki tüm malzemelerin güncel fiyatlarını, stok durumlarını ve eksik parça kodlarını çevrimiçi güncelleyin.
4. Herhangi bir satıra **çift tıklayarak** `MPN`, `LCSC #`, `DigiKey #` veya `Birim Fiyat` bilgilerini manuel olarak da düzenleyebilirsiniz.
5. Sağ alttan istediğiniz formatı (**Genel Mühendislik BOM**, **JLCPCB / LCSC PCBA BOM**, **DigiKey Toplu Sipariş CSV**) seçip **`💾 BOM CSV Olarak Dışa Aktar...`** butonuna tıklayın.

---

### ⚙️ 3. Sekme: Kütüphane ve API Ayarları
* **Kütüphane Kapsamı:** İndirilen komponentlerin **Global Kütüphane** klasörüne mi yoksa sadece **Aktif Proje Klasörü** (`${KIPRJMOD}/Libraries`) içine mi kaydedileceğini seçebilirsiniz.
* **Kütüphane Ön Eki:** Varsayılan `ARI_` ön ekini (örn. `ARI_Resistors.kicad_sym`) kendi tercihinize göre değiştirebilirsiniz.
* **DigiKey API v4 Ayarları:** [DigiKey Developer Portal](https://developer.digikey.com/) üzerinden ücretsiz alacağınız **Product Information API v4** `Client ID` ve `Client Secret` anahtarlarını girip **`🔑 DigiKey API Bağlantısını Test Et`** butonuyla doğrulayabilirsiniz.

---

## 4. Kütüphane Klasör Yapısı

Varsayılan Global Kütüphane dizini (`E:\PCB_Workspace\PCB_Library\LC_DK_Library` veya `Belgeler\KiCad\10.0\libraries\LC_DK_Library`) altında dosyalar şu şekilde organize edilir:

```text
LC_DK_Library/
├── symbols/
│   ├── ARI_Resistors.kicad_sym
│   ├── ARI_Capacitors.kicad_sym
│   ├── ARI_ICs_MCUs.kicad_sym
│   └── ... (14 kategori)
├── footprints/
│   ├── ARI_Resistors.pretty/
│   │   └── *.kicad_mod
│   ├── ARI_ICs_MCUs.pretty/
│   │   └── *.kicad_mod
│   └── ...
└── 3dmodels/
    ├── ARI_Resistors.3dshapes/
    │   └── *.step / *.wrl
    ├── ARI_ICs_MCUs.3dshapes/
    │   └── *.step / *.wrl
    └── ...
```
