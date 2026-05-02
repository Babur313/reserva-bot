-- ════════════════════════════════════════════
-- RESERVA — SQL схема для Supabase
-- Выполнить в: Supabase → SQL Editor → New query
-- ════════════════════════════════════════════

-- ПОЛЬЗОВАТЕЛИ (клиенты)
create table if not exists users (
  id                  bigserial primary key,
  telegram_id         bigint unique not null,
  first_name          text,
  last_name           text,
  username            text,
  phone               text,
  marketing_consent   boolean default false,
  consent_at          timestamptz,
  created_at          timestamptz default now(),
  updated_at          timestamptz default now()
);
create index if not exists users_telegram_id_idx on users(telegram_id);

-- ЗАВЕДЕНИЯ
create table if not exists venues (
  id                  bigserial primary key,
  name                text not null,
  type                text not null check (type in ('restaurant','cafe','hookah','karaoke')),
  type_label          text,
  emoji               text default '🍽️',
  address             text,
  description         text,
  avg_check           text,
  rating              numeric(3,1) default 0,
  reviews_count       int default 0,
  tags                text[] default '{}',
  zones               text[] default '{"Основной зал"}',
  menu_items          jsonb default '[]',
  photos              text[] default '{}',
  video_url           text,
  menu_url            text,
  map_lat             numeric(10,7),
  map_lng             numeric(10,7),
  is_active           boolean default true,
  is_available        boolean default true,
  admin_telegram_id   bigint,
  subscription_plan   text default 'start' check (subscription_plan in ('start','business','pro')),
  subscription_until  date,
  created_at          timestamptz default now()
);

-- БРОНИРОВАНИЯ
create table if not exists bookings (
  id                  bigserial primary key,
  user_telegram_id    bigint references users(telegram_id) on delete set null,
  venue_id            bigint references venues(id) on delete cascade,
  guest_name          text,
  phone               text,
  booking_date        date not null,
  booking_time        time not null,
  guests_count        int default 2 check (guests_count > 0),
  zone                text,
  wishes              text,
  status              text default 'pending' check (status in ('pending','confirmed','cancelled','completed')),
  created_at          timestamptz default now(),
  updated_at          timestamptz default now()
);
create index if not exists bookings_venue_id_idx on bookings(venue_id);
create index if not exists bookings_user_id_idx  on bookings(user_telegram_id);
create index if not exists bookings_date_idx     on bookings(booking_date);

-- ПОДПИСКИ ЗАВЕДЕНИЙ
create table if not exists venue_subscriptions (
  id          bigserial primary key,
  venue_id    bigint references venues(id) on delete cascade,
  plan        text check (plan in ('start','business','pro')),
  price_kzt   int,
  started_at  date default current_date,
  expires_at  date,
  is_active   boolean default true,
  created_at  timestamptz default now()
);

-- ТЕСТОВЫЕ ДАННЫЕ ЗАВЕДЕНИЙ
insert into venues (name, type, type_label, emoji, address, description, avg_check, rating, reviews_count, tags, zones, is_available, subscription_plan) values
(
  'Чайхона №1', 'restaurant', 'Ресторан', '🥩',
  'пр. Назарбаева, 151',
  'Легендарный узбекский ресторан с живой музыкой по пятницам и субботам. Настоящий самаркандский плов, свежие лепёшки из тандыра и уютные дворики.',
  '5 000–9 000 ₸', 4.8, 312,
  ARRAY['🎵 Живая музыка','🌿 Летняя веранда','🍷 Бар','🅿️ Парковка'],
  ARRAY['Основной зал','Летняя веранда','VIP-кабинет'],
  true, 'pro'
),
(
  'Bake & Brew', 'cafe', 'Кафе', '☕',
  'ул. Панфилова, 40',
  'Уютное кафе с авторскими десертами и specialty-кофе от местных обжарщиков. Идеально для рабочих встреч и неспешных завтраков.',
  '2 500–4 000 ₸', 4.6, 187,
  ARRAY['☕ Specialty Coffee','🥐 Авторская выпечка','💻 Wi-Fi'],
  ARRAY['Основной зал','У окна','Диванная зона'],
  true, 'business'
),
(
  'Dubai Lounge', 'hookah', 'Кальянная', '💨',
  'ул. Желтоксан, 87А',
  'Кальянная премиум-класса с арабским интерьером, кальянами на фруктовом льду и широким выбором табаков из ОАЭ.',
  '6 000–12 000 ₸', 4.7, 254,
  ARRAY['💨 Кальян','🎶 DJ по выходным','🌙 Открыто до 4:00'],
  ARRAY['Диваны','VIP-кабины','Открытая терраса'],
  true, 'pro'
),
(
  'Neon Stage', 'karaoke', 'Каракое', '🎤',
  'пр. Достык, 200, ТРЦ Mega',
  'Современный каракое-бар с 12 приватными кабинками и библиотекой из 15 000 треков. Русские, казахские, корейские и международные хиты.',
  '4 000–8 000 ₸', 4.5, 143,
  ARRAY['🎤 15 000 треков','🔒 Приватные кабины','🍕 Кухня до 2:00'],
  ARRAY['Кабина мини (до 8 чел)','Кабина макси (до 15 чел)','Большой зал'],
  false, 'business'
),
(
  'Sakura Garden', 'restaurant', 'Ресторан', '🍣',
  'ул. Кабанбай батыра, 59',
  'Японский ресторан с омакасе-меню от шефа, стажировавшегося в Токио. Живые устрицы, сезонные суши и коктейли на основе sake.',
  '12 000–25 000 ₸', 4.9, 421,
  ARRAY['🍣 Омакасе','🦪 Устрицы','🍶 Sake-бар'],
  ARRAY['Суши-стойка','Основной зал','Чайная комната'],
  true, 'pro'
),
(
  'Green Smoke', 'hookah', 'Кальянная', '🌿',
  'мкр Самал-2, ул. Жолдасбекова, 28',
  'Атмосферная кальянная-антикафе с живыми растениями, беседками и тихой музыкой. Идеально для компании без клубного шума.',
  '3 500–6 000 ₸', 4.4, 98,
  ARRAY['🌿 Уютная атмосфера','🎲 Настольные игры','🍵 Чайная карта'],
  ARRAY['Беседка','Внутренний зал','Балкон'],
  true, 'start'
);

-- RLS (Row Level Security) — опционально на этапе MVP
-- alter table users    enable row level security;
-- alter table bookings enable row level security;
-- ════════════════════════════════════════════════════════
-- RESERVA — Дополнение схемы: модуль меню и предзаказ
-- Выполнить ПОСЛЕ основной схемы (supabase_schema.sql)
-- Supabase → SQL Editor → New query → Run
-- ════════════════════════════════════════════════════════


-- ── КАТЕГОРИИ МЕНЮ ──────────────────────────────────────
create table if not exists menu_categories (
  id          bigserial primary key,
  venue_id    bigint not null references venues(id) on delete cascade,
  name        text   not null,
  sort_order  int    not null default 0,
  created_at  timestamptz default now()
);

create index if not exists menu_categories_venue_idx
  on menu_categories(venue_id, sort_order);


-- ── БЛЮДА ───────────────────────────────────────────────
create table if not exists menu_items (
  id            bigserial primary key,
  venue_id      bigint not null references venues(id)           on delete cascade,
  category_id   bigint not null references menu_categories(id)  on delete cascade,
  name          text   not null,
  price         int    not null check (price > 0),
  description   text   default '',
  media_url     text,                          -- URL в Supabase Storage
  media_type    text   default 'jpg'
                  check (media_type in ('jpg','png','gif','webp')),
  is_hit        boolean default false,
  is_new        boolean default false,
  is_available  boolean default true,
  sort_order    int    not null default 0,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

create index if not exists menu_items_venue_idx
  on menu_items(venue_id, category_id, sort_order);

create index if not exists menu_items_available_idx
  on menu_items(venue_id, is_available);


-- ── ПРЕДЗАКАЗ ────────────────────────────────────────────
-- Позиции предзаказа, привязанные к бронированию
create table if not exists preorder_items (
  id          bigserial primary key,
  booking_id  bigint not null references bookings(id) on delete cascade,
  item_id     bigint references menu_items(id) on delete set null,
  name        text   not null,   -- дублируем на случай удаления блюда
  quantity    int    not null check (quantity > 0),
  price       int    not null,   -- цена на момент заказа
  total       int    not null,   -- price * quantity
  created_at  timestamptz default now()
);

create index if not exists preorder_booking_idx
  on preorder_items(booking_id);


-- ── SUPABASE STORAGE — создать bucket ───────────────────
-- Выполни в Supabase Dashboard → Storage → New bucket:
--   Name:   menu-media
--   Public: true   ← обязательно, иначе фото не загрузятся
--
-- Либо через SQL (если версия Supabase поддерживает):
-- insert into storage.buckets (id, name, public)
-- values ('menu-media', 'menu-media', true)
-- on conflict do nothing;


-- ── ТЕСТОВЫЕ ДАННЫЕ (опционально) ───────────────────────
-- Добавляет меню для первого заведения (id=1, Чайхона №1)

do $$
declare
  v_id   bigint := 1;   -- id заведения «Чайхона №1»
  c1_id  bigint;
  c2_id  bigint;
  c3_id  bigint;
begin

  -- Категория: Горячее
  insert into menu_categories (venue_id, name, sort_order)
  values (v_id, 'Горячее', 0)
  returning id into c1_id;

  insert into menu_items
    (venue_id, category_id, name, price, description, media_type, is_hit, sort_order)
  values
    (v_id, c1_id, 'Плов самаркандский', 2500,
     'Рис, баранина, морковь, нут · 400г', 'gif', true, 0),
    (v_id, c1_id, 'Шашлык из баранины', 3200,
     '300г, приготовлен на мангале', 'jpg', false, 1),
    (v_id, c1_id, 'Лагман', 1800,
     'Домашняя лапша, говядина, овощи · 450г', 'jpg', false, 2);

  -- Категория: Холодные закуски
  insert into menu_categories (venue_id, name, sort_order)
  values (v_id, 'Холодные закуски', 1)
  returning id into c2_id;

  insert into menu_items
    (venue_id, category_id, name, price, description, media_type, is_new, sort_order)
  values
    (v_id, c2_id, 'Салат Ташкент', 1400,
     'Говядина, редька, лук, яйцо · 250г', 'jpg', true, 0),
    (v_id, c2_id, 'Ачичук', 900,
     'Томаты, лук, зелень · 200г', 'jpg', false, 1);

  -- Категория: Напитки
  insert into menu_categories (venue_id, name, sort_order)
  values (v_id, 'Напитки', 2)
  returning id into c3_id;

  insert into menu_items
    (venue_id, category_id, name, price, description, media_type, sort_order)
  values
    (v_id, c3_id, 'Зелёный чай',   400, 'Чайник 500мл',          'jpg', 0),
    (v_id, c3_id, 'Свежевыжатый сок', 900, 'Апельсин / гранат',  'jpg', 1),
    (v_id, c3_id, 'Айран',          350, 'Холодный, 300мл',       'jpg', 2);

end $$;


-- ════════════════════════════════════════════════════════
-- ПАТЧ: язык и город пользователя
-- Выполнить если таблица users уже создана
-- ════════════════════════════════════════════════════════
alter table users
  add column if not exists lang text default 'ru'
    check (lang in ('ru', 'kz', 'en')),
  add column if not exists city text default 'Алматы';
