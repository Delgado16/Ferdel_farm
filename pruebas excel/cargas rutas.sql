CREATE TABLE cargas_ruta (
    ID_Carga INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ID_Ruta INT NOT NULL,
    ID_Asignacion INT NOT NULL,
    Fecha_Carga DATE NOT NULL,
    
    -- Estados del flujo (vendedor verifica en 'Entregada_Camion')
    Estado ENUM('Pendiente', 'Preparada', 'Entregada_Camion', 'Cerrada') DEFAULT 'Pendiente',
    
    -- CONTROL POR VENDEDOR (ÉL VERIFICA)
    Fecha_Hora_Entrega_Camion DATETIME,
    ID_Vendedor_Recibe INT NOT NULL, -- VENDEDOR QUE VERIFICA Y RECIBE
    Observaciones_Vendedor TEXT COMMENT 'Observaciones del vendedor al recibir',
    
    -- Auditoría
    ID_Empresa INT NOT NULL,
    ID_Usuario_Creacion INT COMMENT 'Quién creó la carga (gerente/administrador)',
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    Fecha_Actualizacion DATETIME ON UPDATE CURRENT_TIMESTAMP,
    
    -- Relaciones
    FOREIGN KEY (ID_Ruta) REFERENCES rutas(ID_Ruta),
    FOREIGN KEY (ID_Asignacion) REFERENCES asignacion_vendedores(ID_Asignacion),
    FOREIGN KEY (ID_Vendedor_Recibe) REFERENCES usuarios(ID_Usuario) ON DELETE RESTRICT,
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario),
    
    -- Índices
    INDEX idx_estado (Estado),
    INDEX idx_fecha (Fecha_Carga),
    INDEX idx_vendedor (ID_Vendedor_Recibe)
) ENGINE=InnoDB;

CREATE TABLE detalle_carga_ruta (
    ID_Detalle_Carga INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ID_Carga INT NOT NULL,
    ID_Producto INT NOT NULL,
    
    -- Cantidades en diferentes etapas
    Cantidad_Solicitada DECIMAL(15,2) DEFAULT 0 COMMENT 'Lo que solicita la ruta',
    Cantidad_Despachada DECIMAL(15,2) DEFAULT 0 COMMENT 'Lo que bodega despacha',
    Cantidad_Recibida_Vendedor DECIMAL(15,2) DEFAULT 0 COMMENT 'Lo que VERIFICA el vendedor',
    
    -- Diferencias (automáticas)
    Diferencia AS (Cantidad_Despachada - Cantidad_Recibida_Vendedor),
    
    -- Precios
    Precio_Sugerido DECIMAL(15,2) DEFAULT 0 COMMENT 'Precio sugerido de venta',
    
    -- Auditoría
    ID_Usuario_Actualiza INT COMMENT 'Último usuario que actualizó',
    Fecha_Actualizacion DATETIME ON UPDATE CURRENT_TIMESTAMP,
    
    -- Relaciones
    FOREIGN KEY (ID_Carga) REFERENCES cargas_ruta(ID_Carga) ON DELETE CASCADE,
    FOREIGN KEY (ID_Producto) REFERENCES productos(ID_Producto),
    FOREIGN KEY (ID_Usuario_Actualiza) REFERENCES usuarios(ID_Usuario),
    
    -- Índices
    INDEX idx_carga (ID_Carga),
    INDEX idx_producto (ID_Producto),
    UNIQUE KEY uc_carga_producto (ID_Carga, ID_Producto)
) ENGINE=InnoDB;

CREATE TABLE inventario_ruta (
    ID_Inventario_Ruta INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ID_Ruta INT NOT NULL,
    ID_Producto INT NOT NULL,
    Cantidad_Actual DECIMAL(15,2) DEFAULT 0,
    
    -- Información de la última actualización
    ID_Ultima_Carga INT COMMENT 'Última carga que afectó este inventario',
    Fecha_Ultima_Actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    ID_Usuario_Ultima_Actualizacion INT COMMENT 'Vendedor que hizo la última modificación',
    
    -- Empresa
    ID_Empresa INT NOT NULL,
    
    -- Único por ruta+producto
    UNIQUE KEY uc_ruta_producto (ID_Ruta, ID_Producto, ID_Empresa),
    
    -- Relaciones
    FOREIGN KEY (ID_Ruta) REFERENCES rutas(ID_Ruta),
    FOREIGN KEY (ID_Producto) REFERENCES productos(ID_Producto),
    FOREIGN KEY (ID_Ultima_Carga) REFERENCES cargas_ruta(ID_Carga),
    FOREIGN KEY (ID_Usuario_Ultima_Actualizacion) REFERENCES usuarios(ID_Usuario),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    
    -- Índices
    INDEX idx_ruta (ID_Ruta),
    INDEX idx_producto (ID_Producto)
) ENGINE=InnoDB;

CREATE TABLE movimientos_ruta (
    ID_Movimiento_Ruta INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ID_Ruta INT NOT NULL,
    ID_Producto INT NOT NULL,
    
    -- Tipo de movimiento
    Tipo_Movimiento ENUM('Venta', 'Devolucion', 'Ajuste', 'Carga_Inicial') NOT NULL,
    
    -- Cantidad y precio
    Cantidad DECIMAL(15,2) NOT NULL,
    Precio_Unitario DECIMAL(15,2) NOT NULL DEFAULT 0,
    Subtotal DECIMAL(15,2) NOT NULL DEFAULT 0 COMMENT 'Cantidad * Precio_Unitario',
    
    -- Relaciones con otras entidades
    ID_Carga INT COMMENT 'Carga relacionada (para cargas iniciales)',
    ID_Cliente INT COMMENT 'Cliente si es venta',
    ID_Venta INT COMMENT 'ID de venta si existe en sistema de facturación',
    
    -- Control de inventario
    Saldo_Anterior DECIMAL(15,2) COMMENT 'Saldo antes del movimiento',
    Saldo_Nuevo DECIMAL(15,2) COMMENT 'Saldo después del movimiento',
    
    -- Información adicional
    Observaciones TEXT,
    
    -- Auditoría (EL VENDEDOR REGISTRA)
    ID_Empresa INT NOT NULL,
    ID_Vendedor_Registro INT NOT NULL COMMENT 'VENDEDOR QUE HACE EL MOVIMIENTO',
    Fecha_Hora_Movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Relaciones
    FOREIGN KEY (ID_Ruta) REFERENCES rutas(ID_Ruta),
    FOREIGN KEY (ID_Producto) REFERENCES productos(ID_Producto),
    FOREIGN KEY (ID_Carga) REFERENCES cargas_ruta(ID_Carga),
    FOREIGN KEY (ID_Cliente) REFERENCES clientes(ID_Cliente),
    FOREIGN KEY (ID_Vendedor_Registro) REFERENCES usuarios(ID_Usuario),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    
    -- Índices para consultas frecuentes
    INDEX idx_fecha_movimiento (Fecha_Hora_Movimiento),
    INDEX idx_tipo_movimiento (Tipo_Movimiento),
    INDEX idx_ruta_producto (ID_Ruta, ID_Producto),
    INDEX idx_vendedor (ID_Vendedor_Registro),
    INDEX idx_cliente (ID_Cliente)
) ENGINE=InnoDB;