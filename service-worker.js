// service-worker.js
// Caches every asset the app needs so it keeps working with no network at all
// (once it has been opened online at least once). Cache-first strategy: if a
// file is already cached, serve it instantly; only hit the network for things
// that aren't cached yet, and cache whatever comes back.

const CACHE_NAME = 'monster-cafe-v24';

const PRECACHE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./assets/images/btn_car.png",
  "./assets/images/btn_guruguru.png",
  "./assets/images/btn_seal.png",
  "./assets/images/title.png",
  "./assets/images/haikei.png",
  "./icons/icon-120.png",
  "./icons/icon-152.png",
  "./icons/icon-167.png",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./images/bg_menu.png",
  "./images/bg_seal_boy.png",
  "./images/bg_seal_girl.png",
  "./images/maze_bg.png",
  "./images/maze_road_tile.png",
  "./images/maze_grass_tile.png",
  "./images/maze_car.png",
  "./images/maze_goal.png",
  "./images/maze_goal_safe.png",
  "./images/maze_obstacle_barricade.png",
  "./images/maze_obstacle_puddle.png",
  "./images/maze_start_station.png",
  "./images/maze_bg_intermediate.png",
  "./images/maze_car_police.png",
  "./images/maze_start_police.png",
  "./images/maze_goal_thief.png",
  "./images/maze_goal_thief_caught.png",
  "./images/maze_warp.png",
  "./images/maze_bg_advanced.png",
  "./images/maze_obstacle_cone.png",
  "./images/maze_obstacle_fallen_tree.png",
  "./images/maze_obstacle_trafficjam.png",
  "./images/maze_gimmick_light.png",
  "./images/maze_gimmick_switch.png",
  "./images/maze_gimmick_gate.png",
  "./images/maze_badge_hero.png",
  "./images/car_01.png",
  "./images/car_01_shadow.png",
  "./images/car_02.png",
  "./images/car_02_shadow.png",
  "./images/car_03.png",
  "./images/car_03_shadow.png",
  "./images/car_04.png",
  "./images/car_04_shadow.png",
  "./images/car_05.png",
  "./images/car_05_shadow.png",
  "./images/car_06.png",
  "./images/car_06_shadow.png",
  "./images/car_07.png",
  "./images/car_07_shadow.png",
  "./images/car_08.png",
  "./images/car_08_shadow.png",
  "./images/car_09.png",
  "./images/car_09_shadow.png",
  "./images/car_10.png",
  "./images/car_10_shadow.png",
  "./images/car_11.png",
  "./images/car_11_shadow.png",
  "./images/car_12.png",
  "./images/car_12_shadow.png",
  "./images/car_13.png",
  "./images/car_13_shadow.png",
  "./images/car_14.png",
  "./images/car_14_shadow.png",
  "./images/car_15.png",
  "./images/car_15_shadow.png",
  "./images/car_16.png",
  "./images/car_16_shadow.png",
  "./images/car_17.png",
  "./images/car_17_shadow.png",
  "./images/car_18.png",
  "./images/car_18_shadow.png",
  "./images/car_19.png",
  "./images/car_19_shadow.png",
  "./images/car_20.png",
  "./images/car_20_shadow.png",
  "./images/food_aburasoba.png",
  "./images/food_bomb.png",
  "./images/guruguru_パトカー.png",
  "./images/guruguru_しょうぼうしゃ.png",
  "./images/guruguru_きゅうきゅうしゃ.png",
  "./images/guruguru_はしごしゃ.png",
  "./images/guruguru_ショベルカー.png",
  "./images/guruguru_ブルドーザー.png",
  "./images/guruguru_ダンプカー.png",
  "./images/guruguru_クレーンしゃ.png",
  "./images/guruguru_ミキサーしゃ.png",
  "./images/guruguru_トラック.png",
  "./images/guruguru_ゴミしゅうしゅうしゃ.png",
  "./images/guruguru_カーキャリア.png",
  "./images/guruguru_タンクローリー.png",
  "./images/guruguru_ロードローラー.png",
  "./images/monster_angry.png",
  "./images/monster_eat.png",
  "./images/monster_happy.png",
  "./images/monster_normal.png",
  "./images/monster_sad.png",
  "./images/monster_weird.png",
  "./images/seal_01.png",
  "./images/seal_02.png",
  "./images/seal_03.png",
  "./images/seal_04.png",
  "./images/seal_05.png",
  "./images/seal_06.png",
  "./images/seal_07.png",
  "./images/seal_08.png",
  "./images/seal_09.png",
  "./images/seal_10.png",
  "./images/seal_11.png",
  "./images/seal_12.png",
  "./images/seal_13.png",
  "./images/seal_14.png",
  "./images/seal_15.png",
  "./images/seal_16.png",
  "./images/seal_17.png",
  "./images/seal_18.png",
  "./images/seal_19.png",
  "./images/seal_20.png",
  "./images/seal_21.png",
  "./images/seal_22.png",
  "./images/seal_23.png",
  "./images/seal_24.png",
  "./images/seal_25.png",
  "./images/seal_26.png",
  "./images/seal_27.png",
  "./images/seal_28.png",
  "./images/seal_29.png",
  "./images/seal_30.png",
  "./images/seal_31.png",
  "./images/seal_32.png",
  "./images/seal_33.png",
  "./images/seal_34.png",
  "./images/seal_35.png",
  "./images/seal_36.png",
  "./images/seal_37.png",
  "./images/seal_38.png",
  "./images/seal_39.png",
  "./images/seal_40.png",
  "./images/seal_41.png",
  "./images/seal_42.png",
  "./images/seal_43.png",
  "./images/seal_44.png",
  "./images/seal_45.png",
  "./images/seal_46.png",
  "./images/seal_47.png",
  "./images/seal_48.png",
  "./images/seal_49.png",
  "./images/seal_50.png"
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) { return key !== CACHE_NAME; })
            .map(function(key) { return caches.delete(key); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function(event) {
  if (event.request.method !== 'GET') return;

  // Page loads (navigations) go network-first: iOS home-screen apps rarely
  // re-check the service worker itself, so if we don't also fetch the HTML
  // fresh on every open, an installed home-screen icon can stay stuck on an
  // old version indefinitely. Falls back to the cached shell when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).then(function(response) {
        var responseClone = response.clone();
        caches.open(CACHE_NAME).then(function(cache) {
          cache.put(event.request, responseClone);
        });
        return response;
      }).catch(function() {
        return caches.match(event.request).then(function(cached) {
          return cached || caches.match('./index.html');
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) return cached;
      return fetch(event.request).then(function(response) {
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        var responseClone = response.clone();
        caches.open(CACHE_NAME).then(function(cache) {
          cache.put(event.request, responseClone);
        });
        return response;
      }).catch(function() {
        // offline and not cached: for navigations, fall back to the app shell
        if (event.request.mode === 'navigate') {
          return caches.match('./index.html');
        }
      });
    })
  );
});
