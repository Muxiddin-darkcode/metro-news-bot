import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.filter import is_metro_related
from core.deduplicator import CrossSourceDeduplicator

class TestStrictMetroMonitoring(unittest.TestCase):
    def test_uzbek_metro_news(self):
        # 1. Rasmiy metro kanali xabari (O'zbekcha)
        title_1 = "1,2 MILLIONINCHI YO‘LOVCHINI ANIQLASH ARAFASIDAMIZ!"
        content_1 = "Yangi o‘quv yili boshlanishi bilan Toshkent metropolitenida yo'lovchilar oqimi oshdi."
        is_rel_1, tags_1 = is_metro_related(title_1, content_1)
        self.assertTrue(is_rel_1)
        self.assertIn("#metro", tags_1)

        # 2. Daryo / Kun.uz o'zbekcha xabari
        title_2 = "Toshkent metrosining Chilonzor yo'lida harakat vaqtincha to'xtatildi"
        content_2 = "Texnik nosozlik sababli vagonlar harakatida kechikish kuzatildi."
        is_rel_2, tags_2 = is_metro_related(title_2, content_2)
        self.assertTrue(is_rel_2)
        self.assertIn("#chilonzor", tags_2)

        # 3. O'zbekcha bekat xabari
        title_3 = "Paxtakor bekatida ta'mirlash ishlari o'tkazilmoqda"
        content_3 = "Yo'lovchilar uchun eskalator harakati vaqtincha cheklandi."
        is_rel_3, tags_3 = is_metro_related(title_3, content_3)
        self.assertTrue(is_rel_3)

    def test_russian_tashkent_metro_news(self):
        # Mahalliy Toshkent narx oshishi xabari (Kurbanoff.net)
        title = "С 1 октября предлагается повысить стоимость одной поездки в автобусах и метро"
        content = "В Ташкенте тариф при электронной оплате составит 2500 сум."
        is_rel, tags = is_metro_related(title, content)
        self.assertTrue(is_rel)
        self.assertIn("#metro", tags)

    def test_foreign_and_fake_metro_rejections(self):
        # 1. Tokio/Yaponiya mushuklari xabari (chet el metrosi)
        is_cat, _ = is_metro_related(
            "Кошки спасаются от жары в дренажных тоннелях",
            "В японском метро животные нашли настоящее укрытие от ветра и холода."
        )
        self.assertFalse(is_cat, "Yaponiya metrosi haqidagi mushuklar xabari o'tmasligi shart!")

        # 2. Rossiya Interfax umumiy xabari
        is_interfax, _ = is_metro_related(
            "Что произошло за день: понедельник, 28 сентября",
            "В Москве произошел пожар возле торгового центра Metro Cash and Carry."
        )
        self.assertFalse(is_interfax, "Rossiya va savdo markazi xabari o'tmasligi shart!")

        # 3. Basketbol va Samarqand chempionati
        is_bb, _ = is_metro_related(
            "O'zbekiston basketbol chempionati Samarqandda yakunlandi",
            "G'oliblarga diplom va sovg'alar topshirildi."
        )
        self.assertFalse(is_bb)

        # 4. Ko'chmas mulk / Uy-joy reklamasi
        is_ad, _ = is_metro_related(
            "Chilonzorda metroga yaqin 3 xonali kvartira sotiladi",
            "Yangi ta'mirdan chiqqan, narxi 55000$, telefon: +998901234567"
        )
        self.assertFalse(is_ad, "Metro yaqinidagi kvartira reklamasi o'tmasligi shart!")

        # 5. Sport va yengil atletika masofasi (200 metr yugurish / medal)
        is_sport, _ = is_metro_related(
            "31 медаль за неделю: как Узбекистан выступает на Азиатских играх-2026",
            "на дистанции 200 метров Шохсанам Шерзодова опередила соперниц"
        )
        self.assertFalse(is_sport, "Sportdagi 200 metr masofa metro deb qabul qilinmasligi shart!")


    def test_cross_source_deduplication(self):
        test_cache_file = Path("data/test_fingerprints.json")
        if test_cache_file.exists():
            test_cache_file.unlink()

        dedup = CrossSourceDeduplicator(filepath=test_cache_file, threshold=0.60)

        # 1-Manba (Daryo O'zbekcha)
        title_1 = "Toshkent metrosining Chilonzor yo'lida poyezd to'xtab qoldi"
        content_1 = "Texnik nosozlik sababli vagonlar harakatida 15 daqiqalik kechikish yuzaga keldi."
        is_dup_1, _, _ = dedup.is_duplicate(title_1, content_1, "Telegram / @daryo")
        self.assertFalse(is_dup_1)
        dedup.register_event(title_1, content_1, "Telegram / @daryo", "https://t.me/daryo/101")

        # 2-Manba (Kun.uz O'zbekcha ayni voqea)
        title_2 = "Chilonzor metro yo'lida poyezd to'xtab qoldi: rasmiy ma'lumot"
        content_2 = "Toshkent metrosida texnik nosozlik sababli vagonlar harakati vaqtincha to'xtab qoldi."
        is_dup_2, orig_2, _ = dedup.is_duplicate(title_2, content_2, "Kun.uz")
        self.assertTrue(is_dup_2, "Ayni voqea takrori to'xtatilishi shart!")
        self.assertEqual(orig_2, "Telegram / @daryo")

        if test_cache_file.exists():
            test_cache_file.unlink()

    def test_group_id_and_target_chats(self):
        from config import Settings
        s = Settings(ADMIN_IDS="111,222", GROUP_ID="-100987654321")
        self.assertEqual(s.admin_id_list, [111, 222])
        self.assertEqual(s.group_id_list, [-100987654321])
        self.assertEqual(s.target_chat_ids, [111, 222, -100987654321])

        # Test empty group ID
        s_empty = Settings(ADMIN_IDS="111,222", GROUP_ID="")
        self.assertEqual(s_empty.target_chat_ids, [111, 222])

    def test_custom_keywords_and_explain_filter(self):
        from core.filter import (
            add_custom_keyword,
            remove_custom_keyword,
            get_custom_keywords,
            explain_filter,
            is_metro_related
        )
        test_kw = "yangi toshkent bekati"
        add_custom_keyword(test_kw)
        self.assertIn(test_kw, get_custom_keywords())

        # Test filter detection with custom keyword
        title = "Yangi Toshkent bekatida ta'mirlash ishlari boshlandi"
        is_rel, tags = is_metro_related(title, "")
        self.assertTrue(is_rel)

        # Test explain_filter
        res = explain_filter(title, "")
        self.assertTrue(res["is_metro"])
        self.assertTrue(any("Maxsus kalit so'z" in m for m in res["matched"]))

        # Cleanup
        remove_custom_keyword(test_kw)
        self.assertNotIn(test_kw, get_custom_keywords())

    def test_storage_and_deduplicator_cache_control(self):
        from core.storage import storage
        from core.deduplicator import deduplicator

        storage.mark_seen("http://test.url/1")
        self.assertGreater(storage.count, 0)
        c = storage.clear()
        self.assertGreaterEqual(c, 1)
        self.assertEqual(storage.count, 0)

        # Deduplicator threshold & history
        deduplicator.set_threshold(0.75)
        self.assertEqual(deduplicator.threshold, 0.75)
        deduplicator.register_event("Test Metro Sarlavhasi", "Detallar", "Test Manba", "http://test.url/2")
        self.assertGreater(len(deduplicator.get_recent_events()), 0)
        c2 = deduplicator.clear_history()
        self.assertGreaterEqual(c2, 1)
        self.assertEqual(len(deduplicator.get_recent_events()), 0)

    def test_source_manager_admin_features(self):
        from parsers.manager import SourceManager
        import tempfile
        import json

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump({"telegram_channels": [{"username": "initial_channel", "name": "Init"}], "web_sources": []}, f)
            temp_path = Path(f.name)

        mgr = SourceManager(sources_file=temp_path)
        # Test pause/resume
        self.assertFalse(mgr.is_paused)
        mgr.pause()
        self.assertTrue(mgr.is_paused)
        mgr.resume()
        self.assertFalse(mgr.is_paused)
        mgr.toggle_pause()
        self.assertTrue(mgr.is_paused)

        # Test add/remove telegram
        ok, _ = mgr.add_telegram_channel("test_channel_123", name="Test Channel")
        self.assertTrue(ok)
        self.assertTrue(any(c["username"] == "test_channel_123" for c in mgr.telegram_channels))

        # Test remove telegram
        ok2, _ = mgr.remove_telegram_channel("test_channel_123")
        self.assertTrue(ok2)
        self.assertFalse(any(c["username"] == "test_channel_123" for c in mgr.telegram_channels))

        # Test add/remove web source
        ok_w, _ = mgr.add_web_source("Test Sayt", "https://test.uz", "https://test.uz/rss")
        self.assertTrue(ok_w)
        self.assertTrue(any(w["name"] == "Test Sayt" for w in mgr.web_sources))

        ok_w2, _ = mgr.remove_web_source("Test Sayt")
        self.assertTrue(ok_w2)
        self.assertFalse(any(w["name"] == "Test Sayt" for w in mgr.web_sources))

        if temp_path.exists():
            temp_path.unlink()

if __name__ == "__main__":
    unittest.main()


