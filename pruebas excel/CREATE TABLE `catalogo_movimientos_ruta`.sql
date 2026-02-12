CREATE TABLE `catalogo_movimientos_ruta` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB;

CREATE TABLE `inventario_ruta` (
    `ID_Inventario_Ruta` int NOT NULL AUTO_INCREMENT,
    `ID_Asignacion` int NOT NULL,
    `ID_Producto` int NOT NULL,
    `Cantidad` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Precio_Venta_Ruta` decimal(12,2) DEFAULT NULL,
    `Fecha_Actualizacion` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`ID_Inventario_Ruta`),
    UNIQUE KEY `uk_producto_asignacion_lote` (`ID_Asignacion`, `ID_Producto`, `Lote`),
    KEY `idx_producto` (`ID_Producto`),
    KEY `idx_asignacion` (`ID_Asignacion`),
    CONSTRAINT `fk_inv_ruta_asignacion` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`) ON DELETE CASCADE,
    CONSTRAINT `fk_inv_ruta_producto` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB;

CREATE TABLE `movimientos_ruta_cabecera` (
    `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
    
    -- Vínculos principales
    `ID_Asignacion` int NOT NULL,
    `ID_TipoMovimiento` int NOT NULL,
    `Fecha_Movimiento` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Usuarios responsables
    `ID_Usuario_Registra` int NOT NULL,
    `ID_Usuario_Autoriza` int DEFAULT NULL,
    
    -- Documento soporte
    `Documento_Tipo` enum('FACTURA','FACTURA_COMERCIAL','RECIBO','NOTA_CREDITO','GUIA','INTERNO') DEFAULT NULL,
    `Documento_Serie` varchar(20) DEFAULT NULL,
    
    -- Entidades relacionadas (TUS TABLAS)
    `ID_Cliente` int DEFAULT NULL,
    `ID_Proveedor` int DEFAULT NULL,
    `ID_Factura` int DEFAULT NULL COMMENT 'ID_Factura de tu tabla facturacion',
    `ID_Pedido` int DEFAULT NULL COMMENT 'ID_Pedido de tu tabla pedidos',
    
    -- Totales del movimiento
    `Total_Productos` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Items` int NOT NULL DEFAULT '0',
    `Total_Subtotal` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Monto_Efectivo` decimal(12,2) DEFAULT '0.00',
    
    -- Estado y control
    `ID_Empresa` int NOT NULL,
    `Estado` enum('ACTIVO','ANULADO','PENDIENTE') DEFAULT 'ACTIVO',
    `Fecha_Anulacion` datetime DEFAULT NULL,
    `ID_Usuario_Anula` int DEFAULT NULL,
    `Motivo_Anulacion` text,
    
    PRIMARY KEY (`ID_Movimiento`),
    KEY `idx_asignacion` (`ID_Asignacion`),
    KEY `idx_tipo` (`ID_TipoMovimiento`),
    KEY `idx_fecha` (`Fecha_Movimiento`),
    KEY `idx_cliente` (`ID_Cliente`),
    KEY `idx_proveedor` (`ID_Proveedor`),
    KEY `idx_factura` (`ID_Factura`),
    KEY `idx_pedido` (`ID_Pedido`),
    KEY `idx_documento` (`Documento_Numero`),
    KEY `idx_estado` (`Estado`),
    
    CONSTRAINT `fk_movcab_asignacion` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
    CONSTRAINT `fk_movcab_tipo` FOREIGN KEY (`ID_TipoMovimiento`) REFERENCES `catalogo_movimientos` (`ID_TipoMovimiento`),
    CONSTRAINT `fk_movcab_usuario_reg` FOREIGN KEY (`ID_Usuario_Registra`) REFERENCES `usuarios` (`ID_Usuario`),
    CONSTRAINT `fk_movcab_usuario_aut` FOREIGN KEY (`ID_Usuario_Autoriza`) REFERENCES `usuarios` (`ID_Usuario`),
    CONSTRAINT `fk_movcab_usuario_anu` FOREIGN KEY (`ID_Usuario_Anula`) REFERENCES `usuarios` (`ID_Usuario`),
    CONSTRAINT `fk_movcab_cliente` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`) ON DELETE SET NULL,
    CONSTRAINT `fk_movcab_proveedor` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`) ON DELETE SET NULL,
    CONSTRAINT `fk_movcab_factura` FOREIGN KEY (`ID_Factura`) REFERENCES `facturacion` (`ID_Factura`) ON DELETE SET NULL,
    CONSTRAINT `fk_movcab_pedido` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`) ON DELETE SET NULL,
    CONSTRAINT `fk_movcab_empresa` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB COMMENT='CABECERA - Movimientos de ruta';

CREATE TABLE `movimientos_ruta_detalle` (
    `ID_Detalle` int NOT NULL AUTO_INCREMENT,
    `ID_Movimiento` int NOT NULL,
    `ID_Producto` int NOT NULL,
    `Cantidad` decimal(12,2) NOT NULL,
    `Costo_Unitario` decimal(12,2) DEFAULT NULL,
    `Subtotal` decimal(12,2) NOT NULL,
    `ID_Movimiento_Origen` int DEFAULT NULL,
    `ID_Detalle_Origen` int DEFAULT NULL,
    PRIMARY KEY (`ID_Detalle`),
    KEY `idx_movimiento` (`ID_Movimiento`),
    KEY `idx_producto` (`ID_Producto`),
    KEY `idx_lote` (`Lote`),
    KEY `idx_movimiento_origen` (`ID_Movimiento_Origen`),
    
    CONSTRAINT `fk_movdet_movimiento` FOREIGN KEY (`ID_Movimiento`) REFERENCES `movimientos_ruta_cabecera` (`ID_Movimiento`) ON DELETE CASCADE,
    CONSTRAINT `fk_movdet_producto` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB COMMENT='DETALLE - Productos del movimiento en ruta';

CREATE TABLE `cierres_ruta` (
    `ID_Cierre` int NOT NULL AUTO_INCREMENT,
    `ID_Asignacion` int NOT NULL,
    `Fecha_Cierre` date NOT NULL,
    `Hora_Cierre` time DEFAULT NULL,
    
    -- Control de efectivo
    `Efectivo_Inicial` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Efectivo_Final_Declarado` decimal(12,2) NOT NULL,
    `Efectivo_Final_Calculado` decimal(12,2) NOT NULL,
    `Diferencia_Efectivo` decimal(12,2) GENERATED ALWAYS AS (`Efectivo_Final_Declarado` - `Efectivo_Final_Calculado`) STORED,
    
    -- Totales del día
    `Total_Ventas_Contado` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Ventas_Credito` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Cobros` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Gastos` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Compras` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Devoluciones` decimal(12,2) NOT NULL DEFAULT '0.00',
    `Total_Perdidas` decimal(12,2) NOT NULL DEFAULT '0.00',
    
    -- Estado
    `Estado` enum('ABIERTO','CERRADO','REVISADO') DEFAULT 'ABIERTO',
    `ID_Usuario_Cierre` int DEFAULT NULL,
    `Observaciones` text,
    `ID_Empresa` int NOT NULL,
    
    PRIMARY KEY (`ID_Cierre`),
    UNIQUE KEY `uk_cierre_dia` (`ID_Asignacion`, `Fecha_Cierre`),
    KEY `idx_fecha` (`Fecha_Cierre`),
    KEY `idx_estado` (`Estado`),
    
    CONSTRAINT `fk_cierre_asignacion` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
    CONSTRAINT `fk_cierre_usuario` FOREIGN KEY (`ID_Usuario_Cierre`) REFERENCES `usuarios` (`ID_Usuario`),
    CONSTRAINT `fk_cierre_empresa` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB COMMENT='Cierre diario de ruta';