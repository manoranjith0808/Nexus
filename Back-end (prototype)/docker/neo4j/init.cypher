// ── Constraints ──
CREATE CONSTRAINT persona_id IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_id IS UNIQUE;
CREATE CONSTRAINT cuenta_id IF NOT EXISTS FOR (c:Cuenta) REQUIRE c.cuenta_id IS UNIQUE;
CREATE CONSTRAINT dispositivo_id IF NOT EXISTS FOR (d:Dispositivo) REQUIRE d.device_id IS UNIQUE;
CREATE CONSTRAINT ip_address IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE;
CREATE CONSTRAINT transaccion_id IF NOT EXISTS FOR (t:Transaccion) REQUIRE t.tx_id IS UNIQUE;
CREATE CONSTRAINT entidad_id IF NOT EXISTS FOR (e:EntidadExterna) REQUIRE e.entity_id IS UNIQUE;

// ── Indexes ──
CREATE INDEX persona_doc IF NOT EXISTS FOR (p:Persona) ON (p.document_number);
CREATE INDEX cuenta_country IF NOT EXISTS FOR (c:Cuenta) ON (c.country);
CREATE INDEX transaccion_ts IF NOT EXISTS FOR (t:Transaccion) ON (t.timestamp);
CREATE INDEX ip_risk IF NOT EXISTS FOR (i:IP) ON (i.risk_level);
