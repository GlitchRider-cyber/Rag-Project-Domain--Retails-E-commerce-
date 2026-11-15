import React from 'react';

/**
 * ProductCard component to render structured product info nicely.
 */
export default function ProductCard({ metadata, name, price, sku, inStock, category }) {
  const meta = metadata || {};
  const productName = name || meta.name || 'Product Details';
  const productPrice = price !== undefined ? price : meta.price;
  const productSku = sku || meta.sku;
  const isAvailable = inStock !== undefined ? inStock : meta.in_stock;
  const prodCategory = category || meta.category;

  return (
    <div className="product-card">
      <div className="product-card-header">
        <div className="product-card-title-group">
          <span className="product-card-category">{prodCategory || 'Aurelia Collection'}</span>
          <h4 className="product-card-name">{productName}</h4>
        </div>
        {productPrice !== undefined && (
          <span className="product-card-price">${productPrice}</span>
        )}
      </div>

      <div className="product-card-meta">
        {productSku && (
          <span className="product-card-sku">SKU: <code>{productSku}</code></span>
        )}
        {isAvailable !== undefined && (
          <span className={`stock-badge ${isAvailable ? 'in-stock' : 'out-of-stock'}`}>
            {isAvailable ? 'In Stock' : 'Out of Stock'}
          </span>
        )}
      </div>

      {meta.sizes && meta.sizes.length > 0 && (
        <div className="product-card-sizes">
          <span className="label">Sizes:</span>
          {meta.sizes.map((s, idx) => (
            <span key={idx} className="size-pill">{s}</span>
          ))}
        </div>
      )}

      {meta.colors && meta.colors.length > 0 && (
        <div className="product-card-colors">
          <span className="label">Colors:</span>
          <span className="value">{meta.colors.join(', ')}</span>
        </div>
      )}

      {meta.material && (
        <div className="product-card-material">
          <span className="label">Material:</span>
          <span className="value">{meta.material}</span>
        </div>
      )}
    </div>
  );
}
