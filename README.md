# SwitchShelf

**SwitchShelf**, projeler arasında geçişin görünmeyen maliyetini azaltmak için tasarlanmış, yerel çalışan bir Python iş sürekliliği aracıdır. Ara verirken hedefi, bir sonraki somut adımı, varsa engeli ve işin tamamlandığını nasıl anlayacağını kaydedersin. Geri döndüğünde değişiklikleri görür; aynı kanıtları her yapay zekâ ajanına taşınabilir bir başlangıç brifingine çevirebilirsin.

SwitchShelf kaynak kodunu kopyalamaz, diff içeriğini saklamaz ve projede komut çalıştırmaz. Amaç, kendi gelecekteki haline güvenli ve küçük bir “nerede kalmıştım?” paketi bırakmaktır.

**Farkı:** SwitchShelf konuşmaları veya ajan etkinliğini gözetlemez. İnsanın yazdığı kısa bir devam sözleşmesini depodan gözlenen sinyallerden ayrı tutar; istersen projeye yeniden ısınmanın kaç dakika sürdüğünü kendin kaydedersin. Böylece yalnızca sıradaki adımı saklamaz, kendi devir alışkanlığının işe yarayıp yaramadığını zaman içinde görürsün.

Tam akış ve örnek kayıt için [kullanım örneğine](docs/EXAMPLE.md) göz at.

## Neden SwitchShelf?

Bağlam değiştirmek kolay; bir hafta sonra işe dönüp hangi dosyanın neden değiştiğini hatırlamak daha zor. Git commitleri kod geçmişini anlatır, ancak yarım kalan düşünceyi veya son oturumdan beri nelerin değiştiğini tek yerde toplamaz.

SwitchShelf bu boşluğu yerel bir kontrol noktasıyla doldurur:

- Ara verirken isteğe bağlı kısa not kaydeder.
- Farklı depolardaki son notları ve bekleyen işleri tek bir kuyrukta listeler.
- Hedef, sıradaki eylem, engel ve tamamlanma ölçütüyle eksiksiz bir devir sözleşmesi oluşturur.
- Notu ve gözlenen proje sinyallerini ayıran, model bağımsız devam brifingi üretir.
- Geri dönüş süresini ve kişisel sürtünme puanını isteğe bağlı kaydeder; el değiştirme kalitesini kendi verinle karşılaştırır.
- Geri döndüğünde dosya envanterini önceki kontrol noktasıyla karşılaştırır.
- Git dalı, commit kimliği, çalışma ağacı ve son commit tarihlerini özetler.
- TODO, FIXME, HACK ve BUG işaretlerinin yalnızca dosya, satır ve tür bilgisini toplar.
- Kaynağı, diff metnini, commit mesajını veya uzak Git adresini saklamaz.
- İnternet bağlantısı veya çalışma zamanı bağımlılığı gerektirmez.

## Hızlı başlangıç

Python 3.11 veya yenisini kurduktan sonra proje klasörüne geç. Windows PowerShell'de kurulum yapmadan çalıştırmak için:

    $env:PYTHONPATH = "$PWD\src"
    python -m switchshelf --help

Bu ayar yalnızca açık olan PowerShell penceresinde geçerlidir. Kalıcı komut kurmak istersen, `pip` içeren standart bir Python dağıtımıyla proje klasöründe:

    python -m pip install .

macOS/Linux'ta modül adı çoğunlukla `python3` olur:

    python3 -m pip install .

Ardından şu komutları kullan:

    python -m switchshelf pause . --goal "Önbellek geçersizleştirme davranışını tamamla" --next "Tam kapasite için tahliye yolunu incele" --done-when "Sınır ve hata durumları belgelenip doğrulanınca"
    python -m switchshelf resume .
    python -m switchshelf last .
    python -m switchshelf queue
    python -m switchshelf prompt . --export handoff.md

Komut adı tanınmazsa Python modülü olarak çalıştırabilirsin:

    python -m switchshelf pause . --note "Sonraki adım: hata durumunu incele."
    python -m switchshelf resume .

Kurulum yapmadan modül olarak çalıştırmak için önce `PYTHONPATH` ayarını yapıp `python -m switchshelf` kullan. `pip` ve proje kurulumu varsa, `python -m` bölümünü bırakıp doğrudan `switchshelf` komutunu çağırabilirsin.

SwitchShelf, ilk kez `pause` komutu çalıştırılana kadar kontrol noktası oluşturmaz.

## Kullanım

### Ara verirken kontrol noktası kaydet

    switchshelf pause C:\work\my-project --goal "API önbelleğini güvenli biçimde tamamla" --next "Tam kapasitedeki tahliyeyi incele" --blocker "Yok" --done-when "Sınır ve hata durumları belgelenip doğrulanınca"

Komut proje envanterini yerel kullanıcı veri klasörüne kaydeder ve o ana kadarki bilgileri gösterir. Yeni kontrol noktası öncekinin yerini alır. Dört alan da isteğe bağlıdır; en güçlü devam brifingi için hedef, sıradaki adım ve tamamlanma ölçütünü yaz.

### Geri döndüğünde farkı gör

    switchshelf resume C:\work\my-project

SwitchShelf son kaydı güncellemez; böylece daha sonra tekrar karşılaştırabilirsin. Yeni bir başlangıç noktası oluşturmak için `pause` komutunu yeniden çalıştır.

### Son kaydı tarama yapmadan göster

    switchshelf last C:\work\my-project

### Projeler arası bekleyen işler kuyruğu

    switchshelf queue

Bu komut yerel kontrol noktalarını en yeniden eskiye listeler; proje adı, dal, son kayıttaki değişmiş dosya sayısı, yapılandırılmış devir alanlarının kaçının dolu olduğunu ve sıradaki eylemi (yoksa kısa notu) gösterir. Kuyruk raporunu dışa aktarmak için `--export FILE` ekle.

Kuyrukta görünen kısa ID, klasör taşındıysa veya aynı adlı birden fazla proje varsa kaydı bulmana yardım eder.

### Herhangi bir yapay zekâ ajanına devam brifingi ver

    switchshelf prompt C:\work\my-project --export handoff.md

Brifing, insanın yazdığı hedefi ve sıradaki adımı; taramanın gözlediği dalı, değişen yol adlarını ve görev işaretlerini ayrı bölümlerde sunar. Kaynak kodu ve diff içermez. Taşınabilir Markdown'ı inceleyip istediğin asistana yapıştırabilirsin. Brifing, son taramadaki kanıtların güncel ortamda yeniden doğrulanmasını ister.

### Bağlam değiştirme maliyetini ölç

İşe dönüp ilk anlamlı adımını attıktan sonra, ne kadar sürdüğünü ve geri dönüşü ne kadar zor bulduğunu kendin kaydet:

    switchshelf reflect C:\work\my-project --minutes 7 --friction 2
    switchshelf insights

Bu ölçüm tamamen isteğe bağlıdır. SwitchShelf kendiliğinden zaman tutmaz veya etkinliğini izlemez. `insights`, yeterli sayıda gözlem varsa eksiksiz devir alanlarıyla kısmi devirleri karşılaştırır; bu kişisel bir gözlemsel karşılaştırmadır, nedensellik iddiası değildir. Kayıtta proje adı, not, dosya yolu ve içerik bulunmaz.

### Yerel kontrol noktasını sil

    switchshelf forget C:\work\my-project --yes
    switchshelf forget --id a1b2c3d4 --yes

İlk biçim proje yoluna, ikinci biçim kuyruktaki kısa ID'ye göre yalnızca SwitchShelf'in yerel kaydını siler. Onay bayrağı olmadan çalışmaz.

### Raporu Markdown olarak dışa aktar

    switchshelf resume . --export return-report.md

Mevcut bir rapor dosyasının üzerine yazma varsayılan olarak engellenir. Bilerek değiştirmek için `--overwrite` ekle.

### Gürültülü veya özel yolları dışarıda bırak

    switchshelf pause . --exclude "fixtures/**" --exclude "customer-data/*"

Desenler proje köküne göre eşleştirilir. Git deposunda Git’in standart ignore kuralları da kullanılır. Git deposu olmayan klasörde yaygın derleme/önbellek klasörleri ve hassas adlar atlanır; ek kurallar için `--exclude` kullan.

### Kendi yerel kayıt klasörünü seç

    switchshelf pause . --state-dir D:\private\switchshelf-state
    switchshelf resume . --state-dir D:\private\switchshelf-state

`--state-dir` değerini `pause`, `resume`, `last`, `queue`, `forget`, `prompt`, `reflect` ve `insights` komutlarında aynı tut.

### Sınırları ayarla

    switchshelf pause . --max-files 5000 --max-todos 40

Envanter en fazla 20.000 dosyaya, görev işaretleri en fazla 300 kayda sınırlandırılır. Büyük depolarda taramayı daraltabilir veya `--exclude` kullanabilirsin.

## Neler kaydedilir?

Kontrol noktası JSON dosyası, bilgisayardaki kullanıcıya ait yerel veri dizinine yazılır:

- Windows: `%LOCALAPPDATA%\SwitchShelf`
- macOS: `~/Library/Application Support/SwitchShelf`
- Linux: `$XDG_STATE_HOME/switchshelf` veya `~/.local/state/switchshelf`

Bir kontrol noktasında proje adı, göreli dosya yolları, dosya boyutu ve değişiklik zamanı, yaygın proje dosyalarının adları, dil türü sayımları, görev işareti konumları, Git dalı/commit kimliği/çalışma ağacı yolları, serbest notun ve yazdığın devir alanları bulunabilir. Yıllık isteğe bağlı ölçüm dosyası yalnızca zaman damgalarını, öz bildirim dakika/sürtünme puanını ve devir alanı sayısını saklar; hangi projeye ait olduğunu kaydetmez.

Kontrol noktası tüm dosya adlarını ve dosya ölçülerini karşılaştırma için tutar. Bu bilgiler kaynak metni değildir; yine de özel proje yapısını açığa çıkarabilir. Dışa aktarılmış raporu başkasıyla paylaşmadan önce gözden geçir.

## Gizlilik ve güvenlik sınırları

- Kaynak dosyalarının içeriği, Git diff içeriği, commit mesajları ve uzak depo URL’leri rapora veya kontrol noktasına yazılmaz.
- TODO taraması uygun metin dosyalarını bellekte okur; yalnızca işaret adı (`TODO` gibi), göreli yol ve satır numarası saklanır. İşaretin yanındaki yorum metni atılır.
- `.env`, özel anahtar uzantıları, kimlik bilgisi adları ve yaygın üretim/önbellek klasörleri ad kurallarıyla atlanır. Bu liste sezgiseldir; her özel dosya adını tanıması garanti değildir.
- Göreli yollar, Git dal adları ve kendi notun hassas bilgi içerebilir. Araç rapor paylaşımından önce incelemeni önerir.
- `prompt` dış servise kendi başına hiçbir şey göndermez; oluşturduğu Markdown'ı başka bir hizmete yapıştırırsan brifing metni o hizmete gider.
- `reflect` ölçümü yalnızca sen komut verdiğinde eklenir; isim, not, dosya yolu veya kaynak içeriği kaydetmez. Ölçümler şifrelenmez ve yerel kullanıcı veri dizininde durur.
- Sembolik bağlantılar takip edilmez. Git komutları `shell=False` ile ve yalnızca okuma amaçlı çağrılır.
- Projenin test, build, kurulum veya çalıştırma komutları hiçbir zaman yürütülmez.
- Karşılaştırma dosya boyutu ve zaman damgasına dayanır; dosya içerikleri hash’lenmez. Aynı boyut ve zaman damgasına sahip farklı içerikler fark edilmeyebilir. Git commit kimliği ayrıca karşılaştırılır.
- Ağ isteği yapılmaz; çalışma zamanı bağımlılığı standart Python kütüphanesiyle sınırlıdır.

## Geliştirici notları

Paket `src` düzenini kullanır. Kurulum sonrası CLI `switchshelf` komutuyla, kurulum olmadan ise `python -m switchshelf` biçiminde çalıştırılır.

Temel akış:

1. Proje kökünü bul ve güvenli dosya envanterini oluştur.
2. İnsan tarafından yazılan devir sözleşmesini gözlenen Git/dosya sinyallerinden ayrı sakla.
3. Gerekirse doğrulama uyarıları taşıyan taşınabilir devam brifingi üret.
4. Kullanıcı isterse proje adı veya kimliği toplamadan geri dönüş süresi ve sürtünmesini ölç.

## Lisans

MIT lisansı. Ayrıntılar için `LICENSE` dosyasına bak.
