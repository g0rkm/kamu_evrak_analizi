# CLAUDE.md — Proje Anayasası

## KURAL 1: KOD YAZMA YASAĞI
Claude Code olarak uygulama kaynak kodlarını (.py, .html, .js, .css, .sql vb.) oluşturmak veya düzenlemek için kendi Write, Edit veya MultiEdit araçlarını kullanman KESİNLİKLE YASAKTIR. Tüm uygulama kodu Aider + Argon 4 tarafından yazılır.

## KURAL 2: GÖREV AKTARIM PROTOKOLÜ (.aider_task.md)
Windows PowerShell'de uzun metinlerde tırnak kaçış hataları yaşamamak için, Aider'a vereceğin her detaylı teknik talimatı önce `.aider_task.md` dosyasına yaz. Ardından terminalde şu komutu çalıştır:
```
python -m aider --message-file .aider_task.md <hedef_dosya_1> <hedef_dosya_2>
```

## KURAL 3: MODÜLER İLERLEME VE DENETİM
Projeyi tek seferde değil, mantıksal adımlarla (adım başına 1-2 dosya) Aider'a yazdır. Eğer hedef dosya henüz mevcut değilse önce boş bir dosya oluştur (`New-Item <dosya_adi>`), sonra Aider komutuna parametre olarak ver.

## KURAL 4: KALİTE KONTROL VE TEST
Her Aider çağrısından sonra üretilen kodu `Read` veya `git diff HEAD~1` ile incele, söz dizimi veya çalışma zamanı testlerini terminalde çalıştır. Hata varsa hatayı ve çözüm yolunu `.aider_task.md` içine yazıp yine Aider + Argon 4'e düzelttir.
