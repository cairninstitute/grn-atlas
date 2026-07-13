// Curated starter gene sets, surfaced as one-click entry points into the
// gene-set Analyze panel. Petunia is the classic model for anthocyanin
// (flower pigmentation) regulation, so these lean floral/pigmentation.
//
// Caveat: gene IDs are drawn from the atlas's functional descriptions. The
// flavonoid *structural* genes are reliably identified; the lineage-specific
// master regulators (AN2/AN1/AN11) are NOT cleanly annotated here and are
// omitted rather than guessed — see the planned BLAST-based identification.

export const COLLECTIONS = [
  {
    id: 'petunia-anthocyanin',
    name: 'Petunia — anthocyanin pathway',
    species: 'petunia',
    description: 'Flavonoid structural genes (CHS→UF3GT) plus the BLAST-identified MBW regulatory complex.',
    geneIds: [
      // structural
      'Peaxi162Scf00047g01225', // Chalcone synthase A
      'Peaxi162Scf00164g00313', // Chalcone synthase B
      'Peaxi162Scf00080g01317', // Chalcone isomerase
      'Peaxi162Scf00328g01214', // F3H
      'Peaxi162Scf00150g00218', // F3'5'H
      'Peaxi162Scf00032g00067', // DFR
      'Peaxi162Scf00427g00022', // UF3GT
      // regulators (BLAST-curated identities)
      'Peaxi162Scf00118g00310', // AN2 (master MYB)
      'Peaxi162Scf00338g00912', // AN1 (bHLH)
      'Peaxi162Scf00912g00146', // AN11 (WD40)
      'Peaxi162Scf00119g00942', // JAF13 (bHLH)
      'Peaxi162Scf00349g00057', // PH4 (MYB)
      'Peaxi162Scf01210g00002', // DPL (MYB)
      'Peaxi162Scf00001g00231', // MYB12 (flavonol)
    ],
  },
  {
    id: 'petunia-floral-mads',
    name: 'Petunia — floral MADS-box',
    species: 'petunia',
    description: 'MADS-box / AGAMOUS-like floral-development regulators.',
    geneIds: [
      'Peaxi162Scf00016g00324', // AGAMOUS-like AGL62
      'Peaxi162Scf00274g00457', // AGAMOUS-like 30
      'Peaxi162Scf00008g01613', // MADS-box TF 50
      'Peaxi162Scf00013g00725', // MADS-box TF 18
    ],
  },
];
