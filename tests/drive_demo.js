// 用 Playwright 驱动 demo（月格版）：拖月格游标、点色条开抽屉看实录原文、键盘操作。
// 这是唯一能证明"前端真的能动"的方式 —— 静态截图看不到交互错误。
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  const path = 'file:///C:/Users/31698/projects/guji-pipeline/mingoff/web/demo.html';
  await page.goto(path, { waitUntil: 'load' });
  await page.waitForTimeout(400);

  const out = [];
  const log = s => { out.push(s); console.log(s); };

  // 1. 初始状态（滑块 step=1 = 一个月格）
  log('初始: ' + await page.textContent('#regnal')
      + ' ' + await page.textContent('#monthTag')
      + ' / ' + await page.textContent('#anno'));

  // 2. 画布宽度（无限画布：应远超视口 1440）
  const boardW = await page.evaluate(() => document.getElementById('board').style.width);
  log('画布宽度: ' + boardW + '（视口 1440 → 横向可持续滚动）');

  // 3. 拖到崇祯十年五月（slot = 9*12 + 4 = 112）
  await page.fill('#cursorSlider', '112');
  await page.dispatchEvent('#cursorSlider', 'input');
  await page.waitForTimeout(200);
  log('拖到格 112 → ' + await page.textContent('#regnal')
      + ' ' + await page.textContent('#monthTag')
      + ' / ' + await page.textContent('#anno'));

  // 4. 检查该月高亮
  const stats = await page.evaluate(() => {
    const s = +document.getElementById('cursorSlider').value;
    const bars = [...document.querySelectorAll('.bar')];
    const active = bars.filter(b => !b.classList.contains('is-idle'));
    return { slot: s, total: bars.length, active: active.length,
             names: active.slice(0, 8).map(b => b.textContent) };
  });
  log(`格 ${stats.slot}（崇祯十年五月）：共 ${stats.total} 条，在任 ${stats.active}`);
  log('  在任者样本: ' + stats.names.join('、'));

  // 5. 皇帝行：朱底 + 年龄格
  const reign = await page.evaluate(() => {
    const ages = [...document.querySelectorAll('.reign-age')];
    const bar = document.querySelector('.reign-bar');
    return { ageCount: ages.length, first: ages[0] && ages[0].textContent,
             last: ages[ages.length-1] && ages[ages.length-1].textContent,
             barBg: getComputedStyle(bar).backgroundColor };
  });
  log(`皇帝行: 年龄格 ${reign.ageCount} 个（${reign.first} … ${reign.last}），`
      + `色条底色 ${reign.barBg}（应为朱色 rgb(168,50,45)）`);

  // 6. 点一个色条，看抽屉 + 实录原文
  await page.click('.bar:not(.is-idle)');
  await page.waitForTimeout(400);
  const drawerOpen = await page.evaluate(() =>
    document.getElementById('drawer').classList.contains('open'));
  log('点击色条后抽屉打开: ' + drawerOpen);
  if (drawerOpen) {
    log('  抽屉姓名: ' + await page.textContent('#dName'));
    const shilu = await page.evaluate(() => {
      const blk = document.querySelector('.shilu-block');
      if (!blk) return null;
      return {
        items: blk.querySelectorAll('.shilu-item').length,
        first: blk.querySelector('.shilu-item .src') &&
               blk.querySelector('.shilu-item .src').textContent.slice(0, 50),
      };
    });
    log('  实录原文块: ' + (shilu ? `${shilu.items} 条，首条「${shilu.first}…」` : '无'));
    const fields = await page.evaluate(() =>
      [...document.querySelectorAll('#dBody .field')].map(f => f.textContent.trim().slice(0, 40)));
    fields.slice(0, 4).forEach(f => log('    · ' + f));
  }

  // 7. ESC 关闭
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  log('ESC 后抽屉关闭: ' + await page.evaluate(() =>
    !document.getElementById('drawer').classList.contains('open')));

  // 8. 键盘→步进一个月（不是一年）
  const before = await page.textContent('#monthTag');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(150);
  log(`键盘→ : ${before} → ${await page.textContent('#monthTag')}（应逐月推进）`);

  // 9. 断限：滑到最后一格应为 1644 年 3 月
  await page.evaluate(() => {
    const s = document.getElementById('cursorSlider');
    s.value = s.max; s.dispatchEvent(new Event('input'));
  });
  await page.waitForTimeout(150);
  log('滑到末格 → ' + await page.textContent('#regnal')
      + ' ' + await page.textContent('#monthTag')
      + '（应为崇禎十七年 三月）');

  log('');
  log(errors.length ? ('✗ 控制台错误:\n' + errors.join('\n')) : '✓ 无 JS 报错');
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
