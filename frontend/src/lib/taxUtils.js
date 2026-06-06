/**
 * Dynamic Tax Splitting Formula (Inclusive Pricing)
 * Treats 'total_amount' as tax-inclusive and extracts the parts on-the-fly.
 */
export function calculateTaxSplits(totalAmount, gstPercent = 18) {
  const total = parseFloat(totalAmount || 0);
  const gstRate = parseFloat(gstPercent || 0);

  // Pre-Tax Subtotal = total_amount / (1 + (gst_percent / 100))
  const preTaxSubtotal = total / (1 + (gstRate / 100));
  
  // Total Tax Amount = total_amount - Pre-Tax Subtotal
  const totalTaxAmount = total - preTaxSubtotal;
  
  // Splitting tax split 50/50 for Central and State components
  const cgstAmount = totalTaxAmount / 2;
  const sgstAmount = totalTaxAmount / 2;

  return {
    totalAmount: total,
    gstPercent: gstRate,
    preTaxSubtotal: parseFloat(preTaxSubtotal.toFixed(2)),
    totalTaxAmount: parseFloat(totalTaxAmount.toFixed(2)),
    cgstAmount: parseFloat(cgstAmount.toFixed(2)),
    sgstAmount: parseFloat(sgstAmount.toFixed(2))
  };
}
