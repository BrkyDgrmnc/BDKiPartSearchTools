# BDKiPartSearchTools — Kullanıcı Kılavuzu

**BDKiPartSearchTools**, KiCad (8.0, 9.0 ve 10.0+) kullanıcılarının **LCSC (EasyEDA)**, **DigiKey** ve **Würth Elektronik (Resmi KiCad Kütüphanesi & GitHub)** üzerinden saniyeler içinde komponent aramasını, **Şematik Sembol (`.kicad_sym`)**, **PCB Ayak İzi / Footprint (`.kicad_mod`)** ve **3D Modellerini (`.step` / `.wrl`)** otomatik olarak KiCad kütüphanesine eklemesini ve **anlık fiyat/stok bilgileriyle Malzeme Listesi (BOM)** çıktısı almasını sağlayan hepsi-bir-arada bir KiCad eklentisidir.

---

## 📥 1. Kurulum (Son Kullanıcı İçin)

Herhangi bir ek program veya Python paketi kurmanıza gerek yoktur. Eklenti KiCad'in kendi altyapısıyla doğrudan çalışır.

### Yöntem 1: ZIP Paketi ile Kurulum (GitHub Releases)
1. [GitHub Releases](https://github.com/BrkyDgrmnc/BDKiPartSearchTools/releases) sayfasından en güncel **`com.berkaydegirmenci.bdkipartsearchtools-x.x.x-pcm.zip`** dosyasını bilgisayarınıza indirin *(ZIP dosyasını klasöre çıkartmayın)*.
2. **KiCad** ana penceresini açın ve **`Eklenti ve İçerik Yöneticisi` (Plugin and Content Manager)** butonuna tıklayın.
3. Pencerenin sol alt köşesindeki **`Dosyadan Kur...` (Install from File...)** butonuna tıklayın ve indirdiğiniz `.zip` dosyasını seçin.
4. Sağ alt köşedeki **`Bekleyen Değişiklikleri Uygula` (Apply Pending Changes)** butonuna tıklayın.
5. Kurulum tamamlandıktan sonra KiCad'i kapatıp yeniden açın.

### Yöntem 2: KiCad Eklenti Mağazası (PCM) Üzerinden Kurulum
1. **KiCad -> Eklenti ve İçerik Yöneticisi** penceresini açın.
2. Arama kutusuna **`BDKiPartSearchTools`** yazın.
3. **`Kur` (Install)** butonuna ve ardından **`Bekleyen Değişiklikleri Uygula`** butonuna tıklayın.

---

## 🚀 2. Eklentiyi Açma

Kurulum sonrasında eklentiye hem **Şematik Editörü** hem de **PCB Editörü** içinden ulaşabilirsiniz:

* **Şematik Editöründe (Eeschema):**
  * Üst araç çubuğunun sağ tarafında yer alan **`BD / PS` (`BDKiPartSearchTools`)** ikonuna tıklayın.
  * *(Alternatif)* Üst araç çubuğundaki **`BOM` (Malzeme Listesi Oluştur)** ikonuna tıklayıp listeden **`BDKiPartSearchTools`** seçeneği ile **`Oluştur (Generate)`** butonuna basın.
* **PCB Editöründe (Pcbnew):**
  * Üst araç çubuğundaki **`BD / PS` (`BDKiPartSearchTools`)** ikonuna veya üst menüden **`Araçlar -> Harici Eklentiler -> BDKiPartSearchTools`** seçeneğine tıklayın.

---

## 🛠️ 3. Adım Adım Kullanım

### A) Komponent Arama ve Kütüphaneye Ekleme (`1. Sekme`)

1. **Parça Aratma:**
   * Arama kutusuna aradığınız malzemenin üretici kodunu (`STM32F103C8T6`, `RP2040`, `LM358`), LCSC parça kodunu (`C8734`, `C2040`) veya değerini (`10k 0402`, `100nF 0603`, `USB Type-C`) yazıp **Enter** tuşuna veya **`🔍 Ara`** butonuna basın.
   * Yeni bir arama yapmak istediğinizde **`✖ Temizle`** butonuyla arama kutusunu tek tıkla sıfırlayabilirsiniz.

2. **Canlı 2D Sembol ve Footprint Önizlemesi:**
   * Arama sonuçlarından herhangi bir satıra tıkladığınızda, pencerenin sol alt bölümünde o parçanın **Şematik Sembolü** ve **PCB Footprint** çizimi canlı olarak gösterilir.
   * Footprint önizlemesinin sağ üst köşesinde parçanın 3 boyutlu model durumu (**`3D STEP: Hazır ✓`**) görünür.

3. **Kategori ve Bilgileri Özelleştirme (İsteğe Bağlı):**
   * Eklenti, seçtiğiniz parçanın türünü otomatik algılar ve uygun kategoriyi (`Resistors`, `Capacitors`, `ICs_MCUs`, `Diodes_Protection`, `Transistors_FETs`, `Power_Regulators`, `Connectors` vb.) seçer.
   * Sağ alt panelden `Kategori`, `Sembol Adı`, `Ref Prefix` (`R`, `C`, `U`, `D`...), `Footprint Adı`, `LCSC Parça No`, `DigiKey Parça No` ve `Birim Fiyat` alanlarını kontrol edebilir veya değiştirebilirsiniz.
   * **`📄 Datasheet`** butonuyla parçanın PDF veri sayfasını, **`🌐 LCSC / DigiKey Sayfası`** butonuyla ürün satış sayfasını tarayıcınızda açabilirsiniz.

4. **KiCad Kütüphanesine İçe Aktarma:**
   * **`📥 KiCad Kütüphanesine İçe Aktar (Sembol + Footprint + 3D)`** butonuna tıklayın.
   * Saniyeler içinde parçanın şematik sembolü, PCB footprint'i ve 3D STEP modeli indirilir ve KiCad kütüphane tablolarınıza otomatik kaydedilir.
   * Sembolün içine `Manufacturer`, `MPN`, `LCSC_Part`, `DigiKey_Part`, `Datasheet` ve `Supplier_URL` bilgileri otomatik gömülür (dinamik Fiyat ve Stok bilgisi ise tedarikçi kuralları ve güncellik gereği 2. Sekmedeki BOM yöneticisinde anlık canlı sorgulanır).

5. **Şematiğe Yerleştirme:**
   * **Şematik Editörüne (Eeschema)** dönün, klavyeden **`A`** (*Sembol Ekle*) tuşuna basın ve indirdiğiniz parçanın adını yazıp şematiğinize yerleştirin!
   * Şematikten PCB'ye geçtiğinizde (*Şematikten PCB'yi Güncelle / F8*), parçanın **Footprint**'i ve **3D Görüntüleyicideki (Alt+3) 3 boyutlu STEP modeli** hiçbir ek ayar gerektirmeden otomatik olarak hazır gelir.

---

### B) Fiyatlı ve Stoklu Akıllı BOM Çıktısı Alma (`2. Sekme`)

1. **`📊 2. Akıllı BOM, Fiyat ve Stok Çıktısı`** sekmesine geçin.
2. Açık olan projenizdeki tüm malzemeler otomatik listelenir. Farklı bir projeyi yüklemek isterseniz **`📂 Proje Klasörü Seç...`** butonunu kullanabilirsiniz.
3. **`Üretilecek Kart Adedi (PCB Sayısı)`** kutusuna kaç adet kart üreteceğinizi girin (örneğin `1`, `10`, `50`, `100`). Eklenti, toplam sipariş adedine göre tedarikçinin **kademeli indirimli birim fiyatlarını** ve **toplam parti maliyetini** otomatik hesaplar.
4. **`⚡ Canlı Fiyat, Stok ve Parça Numaralarını Çek (LCSC / DigiKey)`** butonuna tıklayarak tüm malzemelerin en güncel birim fiyatlarını ve stok adetlerini çevrimiçi güncelleyin.
5. Tablodaki herhangi bir satıra **çift tıklayarak** parça numarasını (`MPN`, `LCSC #`, `DigiKey #`) veya birim fiyatını manuel olarak da düzenleyebilirsiniz.
6. Sağ alttaki **`Format`** menüsünden ihtiyacınız olan çıktı tipini seçip **`💾 BOM CSV Olarak Dışa Aktar...`** butonuna tıklayın:
   * **Genel Mühendislik BOM:** `MPN`, `Üretici`, `LCSC #`, `DigiKey #`, `Birim Fiyat ($)`, `1 PCB Maliyeti ($)`, `Toplam Parti Maliyeti ($)`, `Stok`, `Datasheet` ve `Tedarikçi Linkleri` dahil tam detaylı Excel uyumlu tablo.
   * **JLCPCB / LCSC PCBA Uyumlu BOM:** JLCPCB dizgi sipariş sistemine doğrudan yüklenmeye hazır `Comment, Designator, Footprint, LCSC Part #` formatı.
   * **DigiKey Toplu Sipariş (Bulk Upload) CSV:** DigiKey sepetine tek seferde toplu malzeme eklemeye uygun format.

---

### C) Kütüphane ve API Ayarları (`3. Sekme`)

* **Kütüphane Kapsamı:**
  * **Global Kütüphane *(Varsayılan)*:** İndirdiğiniz tüm komponentler tek bir merkezi klasörde toplanır ve tüm KiCad projelerinizde ortak kullanılır.
  * **Aktif Proje Klasörü:** İndirilen komponentler sadece o an çalıştığınız projenin kendi klasörü içine (`${KIPRJMOD}/Libraries`) kaydedilir; projeyi başka bir bilgisayara taşıdığınızda tüm kütüphaneleriyle birlikte gider.
* **Dosya Organizasyonu:**
  * Komponentleri kategorilerine göre ayrı kütüphanelere (`BDKi_Resistors`, `BDKi_Capacitors`, `BDKi_ICs_MCUs` vb.) ayırabilir veya tek bir ortak kütüphane altında toplayabilirsiniz.
* **DigiKey API Bağlantısı *(İsteğe Bağlı)*:**
  * Eklenti, LCSC / EasyEDA aramaları ve CAD (Sembol/Footprint/3D) indirmeleri için **hiçbir API anahtarına ihtiyaç duymadan** kutudan çıktığı gibi çalışır.
  * DigiKey üzerinden de canlı fiyat, stok ve doğrudan arama yapmak isterseniz [developer.digikey.com](https://developer.digikey.com/) adresinden ücretsiz bir uygulama oluşturup **Product Information API v4** `Client ID` ve `Client Secret` bilgilerinizi bu sekmeye girebilir ve **`🔑 DigiKey API Bağlantısını Test Et`** butonuyla bağlantınızı doğrulayabilirsiniz.

---

## ❓ 4. Sıkça Sorulan Sorular (SSS)

* **Soru: Komponenti kütüphaneye ekledim ancak Şematikte `A` (Sembol Ekle) penceresinde hemen görünmedi, ne yapmalıyım?**
  * **Cevap:** KiCad Şematik Editörü (`Eeschema`), kütüphane dosyalarını ilk açılışta belleğe (RAM) alır. Eğer Eeschema açıkken yeni bir parça eklediyseniz, üst menüden **`Tercihler -> Sembol Kütüphanelerini Yönet...` (Preferences -> Manage Symbol Libraries...)** penceresini açıp doğrudan **`Tamam` (OK)** butonuna basmanız (veya Şematik Editörünü kapatıp açmanız) kütüphane listesini anında yenileyecektir.

* **Soru: İndirilen 3D modelleri PCB'ye ayrıca tanıtmam gerekiyor mu?**
  * **Cevap:** Hayır. Eklenti `.step` dosyasını indirirken X/Y/Z konum ve açı hizalamasını otomatik hesaplayıp footprint (`.kicad_mod`) dosyasının içine gömer. PCB Editöründe **3D Görüntüleyiciyi (`Alt + 3`)** açtığınızda 3 boyutlu model doğrudan pedlerin üzerinde hizalı şekilde görünür.

* **Soru: Eklentiyi güncellediğimde ayarlarım veya indirdiğim kütüphaneler silinir mi?**
  * **Cevap:** Hayır. İndirdiğiniz tüm sembol, footprint ve 3D modeller kendi kütüphane klasörünüzde kalır; ayrıca API ayarlarınız ve önbelleğiniz güncellemelerde otomatik olarak korunur.
