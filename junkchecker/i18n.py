"""UI strings. Add a language by adding a dict with the same keys (missing keys fall back to English)."""
import locale

LANGS = {"en": "English", "tr": "Türkçe"}

STRINGS = {
    "en": {
        "app_sub": "Find and clean junk files in EDA / CAD projects",
        "folder": "FOLDER", "browse": "Browse", "scan": "Scan", "cancel": "Cancel",
        "choose_title": "Select the folder to scan",
        "keep_hist": "Keep newest backups", "big_arch": "Large archive (MB)",
        "show": "SHOW", "all": "All", "safe": "Safe to delete", "unknown": "Unknown", "keep": "Kept", "mixed": "Mixed",
        "files": "files",
        "tab_junk": "Junk", "tab_dupes": "Duplicates", "tab_overview": "Overview",
        "col_name": "Folder / file", "col_status": "Status", "col_size": "Size", "col_count": "Files",
        "col_reason": "Reason", "col_mtime": "Modified",
        "select_safe": "Select all safe", "clear": "Clear selection", "open": "Open location",
        "delete": "Clean selected", "selected": "Selected: {n} files, {size}",
        "ready": "Pick a folder and press Scan.", "scanning": "Scanning…", "scanning_n": "Scanning… {n} files",
        "scan_done": "Scan finished at {t}", "cancelled": "Cancelled.", "no_results": "Nothing found.",
        "no_folder_t": "Folder not found", "no_folder_m": "Folder does not exist:\n{p}",
        "scan_err_t": "Scan error", "nothing_t": "Nothing selected",
        "nothing_m": "No files selected (kept files are always excluded).",
        "confirm_t": "Confirm",
        "confirm_recycle": "{n} files ({size}) will be moved to the Recycle Bin.",
        "confirm_move": "{n} files ({size}) will be moved to:\n{dest}",
        "confirm_zip": "{n} files ({size}) will be packed into a zip in:\n{dest}\nand then removed.",
        "unknown_w": "\n\n⚠ {n} of them are 'Unknown':\n{names}{more}\n\nInclude these as well?",
        "and_more": "\n  … and {n} more",
        "eda_running": "⚠ {tools} is running. Close it before cleaning: files of open projects are kept automatically.",
        "deleting": "Cleaning…", "del_err_t": "Error",
        "deleted": "{n} files ({size}) cleaned ({mode}).",
        "mode_recycle": "Recycle Bin", "mode_move": "moved to archive", "mode_zip": "zipped",
        "restore": "Undo last clean", "restore_none": "There is no clean operation to undo.",
        "restore_q": "Restore {n} files cleaned on {t} ({mode})?",
        "restore_done": "{ok} files restored, {fail} could not be restored.",
        "export": "Export report", "export_title": "Save report", "exported": "Report saved: {p}",
        "git": "Git helper", "git_title": "Git helper",
        "git_none": "No git repositories with junk in this scan.",
        "git_info": "JunkChecker never runs git write commands. Copy the commands below and run them yourself.",
        "git_copy": "Copy commands", "git_append": "Append to .gitignore", "git_appended": ".gitignore updated: {p}",
        "git_untrack": "{n} tracked junk files", "git_ignore": "{n} .gitignore suggestions",
        "copied": "Copied to clipboard.",
        "settings": "Settings", "save": "Save", "close": "Close",
        "s_profiles": "RULE PROFILES", "s_edit_rules": "Edit rules file", "s_rules_err": "Rules file error",
        "s_excludes": "EXCLUDED FOLDERS / PATTERNS", "s_add": "Add folder", "s_add_pat": "Add pattern",
        "s_remove": "Remove", "s_pattern_q": "Glob pattern (e.g. *\\Libraries\\*):",
        "s_action": "CLEAN ACTION", "s_dest": "Archive folder", "s_dest_req": "Choose an archive folder for this action.",
        "s_options": "OPTIONS", "s_skip_net": "Skip network drives", "s_protect": "Protect files of open projects",
        "s_dupe_min": "Duplicate minimum size (MB)",
        "s_theme": "Theme", "light": "Light", "dark": "Dark",
        "exclude_this": "Exclude this folder", "excluded_m": "Excluded: {p}",
        "d_scan": "Find duplicates", "d_groups": "{g} groups, {size} wasted",
        "d_select": "Select copies (keep oldest)", "d_col_copies": "Copies", "d_col_wasted": "Wasted",
        "d_hint": "Duplicates are always 'Unknown': check before cleaning.",
        "o_reclaim": "RECLAIMABLE", "o_total": "RECLAIMED (ALL TIME)", "o_30": "LAST 30 DAYS", "o_ops": "OPERATIONS",
        "o_treemap": "Treemap — click a box to zoom in, right-click to zoom out", "o_month": "Reclaimed per month", "o_col_month": "Month",
        "o_empty": "Scan a folder to see the treemap.",
        "r_big-archive": "Large archive — may be a real backup", "r_tracked": " — tracked by git",
        "r_keep": "One of the newest {n} backups", "r_open": "Project is open in an EDA tool",
        "r_dupe": "Duplicate of {p}",
        "cached": "Showing cached results from {t}. Scan again to refresh.",
        "open_data": "Logs & data",
    },
    "tr": {
        "app_sub": "EDA / CAD projelerindeki çöp dosyaları bul ve temizle",
        "folder": "KLASÖR", "browse": "Gözat", "scan": "Tara", "cancel": "İptal",
        "choose_title": "Taranacak klasörü seç",
        "keep_hist": "Saklanacak en yeni yedek", "big_arch": "Büyük arşiv (MB)",
        "show": "GÖSTER", "all": "Hepsi", "safe": "Kesin silinebilir", "unknown": "Bilinmiyor", "keep": "Saklanacak",
        "mixed": "Karışık", "files": "dosya",
        "tab_junk": "Çöp", "tab_dupes": "Kopyalar", "tab_overview": "Genel bakış",
        "col_name": "Klasör / dosya", "col_status": "Durum", "col_size": "Boyut", "col_count": "Dosya",
        "col_reason": "Neden", "col_mtime": "Değiştirilme",
        "select_safe": "Kesin silinebilirleri seç", "clear": "Seçimi temizle", "open": "Konumu aç",
        "delete": "Seçilenleri temizle", "selected": "Seçili: {n} dosya, {size}",
        "ready": "Bir klasör seç ve Tara'ya bas.", "scanning": "Taranıyor…", "scanning_n": "Taranıyor… {n} dosya",
        "scan_done": "Tarama bitti: {t}", "cancelled": "İptal edildi.", "no_results": "Bir şey bulunamadı.",
        "no_folder_t": "Klasör yok", "no_folder_m": "Klasör bulunamadı:\n{p}",
        "scan_err_t": "Tarama hatası", "nothing_t": "Seçim yok",
        "nothing_m": "Dosya seçilmedi (Saklanacak dosyalar her zaman hariç tutulur).",
        "confirm_t": "Onay",
        "confirm_recycle": "{n} dosya ({size}) Geri Dönüşüm Kutusu'na taşınacak.",
        "confirm_move": "{n} dosya ({size}) şuraya taşınacak:\n{dest}",
        "confirm_zip": "{n} dosya ({size}) şu klasörde bir zip'e paketlenip silinecek:\n{dest}",
        "unknown_w": "\n\n⚠ Bunlardan {n} tanesi 'Bilinmiyor' durumunda:\n{names}{more}\n\nBunları da dahil etmek istiyor musun?",
        "and_more": "\n  … ve {n} tane daha",
        "eda_running": "⚠ {tools} açık. Temizlemeden önce kapat: açık projelerin dosyaları otomatik olarak saklanır.",
        "deleting": "Temizleniyor…", "del_err_t": "Hata",
        "deleted": "{n} dosya ({size}) temizlendi ({mode}).",
        "mode_recycle": "Geri Dönüşüm Kutusu", "mode_move": "arşive taşındı", "mode_zip": "zip'lendi",
        "restore": "Son temizliği geri al", "restore_none": "Geri alınacak bir temizlik işlemi yok.",
        "restore_q": "{t} tarihinde temizlenen {n} dosya ({mode}) geri yüklensin mi?",
        "restore_done": "{ok} dosya geri yüklendi, {fail} dosya geri yüklenemedi.",
        "export": "Rapor al", "export_title": "Raporu kaydet", "exported": "Rapor kaydedildi: {p}",
        "git": "Git yardımcısı", "git_title": "Git yardımcısı",
        "git_none": "Bu taramada çöp içeren git deposu yok.",
        "git_info": "JunkChecker git'e yazan komutları asla kendisi çalıştırmaz. Aşağıdaki komutları kopyalayıp kendin çalıştır.",
        "git_copy": "Komutları kopyala", "git_append": ".gitignore'a ekle", "git_appended": ".gitignore güncellendi: {p}",
        "git_untrack": "Takip edilen {n} çöp dosya", "git_ignore": "{n} .gitignore önerisi",
        "copied": "Panoya kopyalandı.",
        "settings": "Ayarlar", "save": "Kaydet", "close": "Kapat",
        "s_profiles": "KURAL PROFİLLERİ", "s_edit_rules": "Kural dosyasını düzenle", "s_rules_err": "Kural dosyası hatası",
        "s_excludes": "HARİÇ TUTULAN KLASÖRLER / DESENLER", "s_add": "Klasör ekle", "s_add_pat": "Desen ekle",
        "s_remove": "Kaldır", "s_pattern_q": "Glob deseni (örn. *\\Libraries\\*):",
        "s_action": "TEMİZLEME YÖNTEMİ", "s_dest": "Arşiv klasörü", "s_dest_req": "Bu yöntem için bir arşiv klasörü seç.",
        "s_options": "SEÇENEKLER", "s_skip_net": "Ağ sürücülerini atla", "s_protect": "Açık projelerin dosyalarını koru",
        "s_dupe_min": "Kopya için en küçük boyut (MB)",
        "s_theme": "Tema", "light": "Açık", "dark": "Koyu",
        "exclude_this": "Bu klasörü hariç tut", "excluded_m": "Hariç tutuldu: {p}",
        "d_scan": "Kopyaları bul", "d_groups": "{g} grup, {size} boşa harcanıyor",
        "d_select": "Kopyaları seç (en eskisi kalsın)", "d_col_copies": "Kopya", "d_col_wasted": "Boşa giden",
        "d_hint": "Kopyalar her zaman 'Bilinmiyor' sayılır: temizlemeden önce kontrol et.",
        "o_reclaim": "KAZANILABİLİR", "o_total": "KAZANILAN (TÜM ZAMANLAR)", "o_30": "SON 30 GÜN", "o_ops": "İŞLEM",
        "o_treemap": "Ağaç haritası — yakınlaşmak için kutuya tıkla, uzaklaşmak için sağ tıkla",
        "o_month": "Aylara göre kazanılan alan", "o_col_month": "Ay", "o_empty": "Ağaç haritası için bir klasör tara.",
        "r_big-archive": "Büyük arşiv — gerçek bir yedek olabilir", "r_tracked": " — git'te takip ediliyor",
        "r_keep": "En yeni {n} yedekten biri", "r_open": "Proje bir EDA aracında açık",
        "r_dupe": "{p} dosyasının kopyası",
        "cached": "{t} tarihli önbellek gösteriliyor. Güncellemek için tekrar tara.",
        "open_data": "Loglar ve veriler",
    },
}


def default_lang():
    try:
        import ctypes
        if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x1F:  # LANG_TURKISH
            return "tr"
    except Exception:
        pass
    loc = (locale.getlocale()[0] or "").lower()
    return "tr" if loc.startswith("tr") or "turkish" in loc else "en"


def upper(text, lang):
    """Locale-correct upper case (Turkish dotted/dotless i)."""
    if lang == "tr":
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


def tr(lang, key, **kw):
    s = STRINGS.get(lang, {}).get(key, STRINGS["en"].get(key, key))
    return s.format(**kw) if kw else s
