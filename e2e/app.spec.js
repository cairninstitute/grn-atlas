import { test, expect } from '@playwright/test';

test.setTimeout(60000);

const goToAnalysis = async (page) => {
  await page.goto('/');
  await page.locator('button:has-text("Analysis")').click();
  await expect(page.locator('.analysis-view')).toBeVisible({ timeout: 5000 });
};

const openPanel = async (page, title) => {
  const header = page.locator('.analysis-card-header', { hasText: title });
  await header.click();
  return page.locator('.analysis-card', { hasText: title });
};

test.describe('App loads', () => {
  test('landing page renders with gene search', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Gene Regulatory Network Atlas')).toBeVisible();
    await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
  });

  test('example gene buttons are present', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=TP53')).toBeVisible();
    await expect(page.locator('text=MYC')).toBeVisible();
  });

  test('view tabs are present', async ({ page }) => {
    await page.goto('/');
    for (const tab of ['Network', 'Organism', 'Pathways', 'Comparison', 'Genome', 'Design', 'Analysis']) {
      await expect(page.locator(`button:has-text("${tab}")`)).toBeVisible();
    }
  });
});

test.describe('Gene search', () => {
  test('searching TP53 loads network view', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("TP53")').click();
    await expect(page.locator('.toolbar')).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Analysis tab', () => {
  test('opens and shows all panel headers', async ({ page }) => {
    await goToAnalysis(page);
    const expectedPanels = [
      'Regulon Extraction', 'Regulon Comparison', 'Upstream Regulators',
      'Network Patterns', 'Centrality Metrics', 'Module Detection',
      'Motif Query', 'Inferred Edges', 'Differential Regulation', 'Edge Export',
    ];
    for (const panel of expectedPanels) {
      await expect(page.locator('.analysis-card-header', { hasText: panel })).toBeVisible();
    }
  });

  test('section headers group panels', async ({ page }) => {
    await goToAnalysis(page);
    for (const section of ['Regulon & Upstream', 'Network Structure', 'Inference & Comparison', 'Export']) {
      await expect(page.locator('.analysis-section-title', { hasText: section })).toBeVisible();
    }
  });

  test('centrality panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Centrality Metrics');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-table')).toBeVisible({ timeout: 15000 });
  });

  test('inferred edges panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Inferred Edges');
    await card.locator('select').first().selectOption('arabidopsis');
    await card.locator('input[type="text"]').fill('AT5G11260');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-table, .analysis-error')).toBeVisible({ timeout: 15000 });
  });

  test('module detection panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Module Detection');
    await card.locator('select').first().selectOption('human');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-stats, .analysis-error')).toBeVisible({ timeout: 45000 });
  });

  test('motif query panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Motif Query');
    await card.locator('input[type="text"]').first().fill('AT5G11260');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-table, .analysis-error')).toBeVisible({ timeout: 15000 });
  });

  test('diff regulation panel shows form and validates', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Differential Regulation');
    await card.locator('select').first().selectOption('arabidopsis');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-error')).toBeVisible({ timeout: 10000 });
  });

  test('export panel has format selector and textarea', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Edge Export');
    await expect(card.locator('select')).toBeVisible();
    await expect(card.locator('textarea')).toBeVisible();
  });

  test('network patterns panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Network Patterns');
    await card.locator('select').first().selectOption('human');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-table')).toBeVisible({ timeout: 15000 });
  });

  test('regulon panel runs query', async ({ page }) => {
    await goToAnalysis(page);
    const card = page.locator('.analysis-card', { hasText: 'Regulon Extraction' }).first();
    await card.locator('input[type="text"]').fill('TP53');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-table')).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Organism view', () => {
  test('organism view loads', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("Organism")').click();
    await expect(page.locator('.organism-view')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Genome view', () => {
  test('genome comparison view loads', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("Genome")').click();
    await expect(page.locator('.genome-view')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Workflow panels', () => {
  test('workflow section headers visible', async ({ page }) => {
    await goToAnalysis(page);
    await expect(page.locator('.analysis-section-title', { hasText: 'Workflows' })).toBeVisible();
    for (const wf of ['Inferred → Enrichment', 'Module → Motif', 'Regulon → Differential', 'Inferred → Validation']) {
      await expect(page.locator('.analysis-card-header', { hasText: wf })).toBeVisible();
    }
  });

  test('inferred → enrichment workflow runs', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Inferred → Enrichment');
    await card.locator('input[type="text"]').fill('AT5G11260');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-stats, .analysis-error')).toBeVisible({ timeout: 15000 });
  });

  test('inferred → validation workflow runs', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Inferred → Validation');
    await card.locator('input[type="text"]').fill('AT5G11260');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-stats, .analysis-error')).toBeVisible({ timeout: 15000 });
  });

  test('module → motif workflow detects modules', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Module → Motif');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-stats, .analysis-error')).toBeVisible({ timeout: 30000 });
  });

  test('regulon → differential workflow validates inputs', async ({ page }) => {
    await goToAnalysis(page);
    const card = await openPanel(page, 'Regulon → Differential');
    await card.locator('.btn-run').click();
    await expect(card.locator('.analysis-error')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('URL state', () => {
  test('clicking analysis tab updates URL', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("Analysis")').click();
    await expect(page).toHaveURL(/view=analysis/);
  });
});
