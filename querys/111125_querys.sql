use db_ferdel;

CREATE TABLE Inventario_Bodega (
    ID_Bodega INT,
    ID_Producto INT,
    Existencias DECIMAL(12,2) DEFAULT 0,
    PRIMARY KEY (ID_Bodega, ID_Producto),
    FOREIGN KEY (ID_Bodega) REFERENCES Bodegas(ID_Bodega),
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
);
drop table Inventario_Bodega;
drop table bodegas;

CREATE TABLE Bodegas (
    ID_Bodega INT PRIMARY KEY AUTO_INCREMENT,
    Nombre VARCHAR(255) NOT NULL,
    Ubicacion VARCHAR(255),
    Estado ENUM('activa', 'inactiva') DEFAULT 'activa',
    ID_Empresa INT NOT NULL,
    Fecha_Creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ID_Empresa) REFERENCES Empresa(ID_Empresa)
);

CREATE TABLE Movimientos_Inventario (
    ID_Movimiento INT PRIMARY KEY AUTO_INCREMENT,
    ID_TipoMovimiento INT NOT NULL,
    N_Factura_Externa VARCHAR(255),
    ID_Factura_Venta INT NULL,
    Fecha DATE NOT NULL,
    ID_Proveedor INT NULL,
    Tipo_Compra ENUM('CONTADO', 'CREDITO') NULL,
    Observacion TEXT,
    ID_Empresa INT NOT NULL,
    ID_Bodega INT NOT NULL,
    ID_Bodega_Destino INT NULL,
    UbicacionEntrega TEXT,
    ID_Usuario_Creacion INT NOT NULL,
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion DATETIME NULL,
    ID_Usuario_Modificacion INT NULL,
    Estado INT DEFAULT 1,
    FOREIGN KEY (ID_TipoMovimiento) REFERENCES Catalogo_Movimientos(ID_TipoMovimiento),
    FOREIGN KEY (ID_Factura_Venta) REFERENCES Facturacion(ID_Factura),
    FOREIGN KEY (ID_Proveedor) REFERENCES Proveedores(ID_Proveedor),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Bodega) REFERENCES Bodegas(ID_Bodega),
    FOREIGN KEY (ID_Bodega_Destino) REFERENCES Bodegas(ID_Bodega),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario),
    FOREIGN KEY (ID_Usuario_Modificacion) REFERENCES usuarios(ID_Usuario),
    -- Índices
    INDEX idx_fecha (Fecha),
    INDEX idx_tipo_movimiento (ID_TipoMovimiento),
    INDEX idx_bodega (ID_Bodega),
    INDEX idx_proveedor (ID_Proveedor),
    INDEX idx_tipo_compra (Tipo_Compra),  -- ← NUEVO ÍNDICE
    INDEX idx_factura_venta (ID_Factura_Venta),
    INDEX idx_usuario_creacion (ID_Usuario_Creacion)
);

CREATE TABLE Detalle_Movimientos_Inventario (
    ID_Detalle_Movimiento INT PRIMARY KEY AUTO_INCREMENT,
    ID_Movimiento INT NOT NULL,
    ID_Producto INT NOT NULL,
    Cantidad DECIMAL(15,4) NOT NULL,
    Costo_Unitario DECIMAL(15,4) DEFAULT 0,
    Precio_Unitario DECIMAL(15,4) DEFAULT 0,
    Subtotal DECIMAL(15,4) DEFAULT 0,
    Lote VARCHAR(100),
    Fecha_Vencimiento DATE,
    ID_Usuario_Creacion INT NOT NULL,
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- Llaves foráneas
    FOREIGN KEY (ID_Movimiento) REFERENCES Movimientos_Inventario(ID_Movimiento) ON DELETE CASCADE,
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario),
    -- Índices
    INDEX idx_movimiento (ID_Movimiento),
    INDEX idx_producto (ID_Producto),
    INDEX idx_lote (Lote)
);

CREATE TABLE Facturacion (
    ID_Factura INT PRIMARY KEY AUTO_INCREMENT,
    Fecha DATE NOT NULL,
    IDCliente INT NOT NULL,
    Tipo_Compra ENUM('CONTADO', 'CREDITO') NULL,
    Observacion TEXT,
    ID_Empresa INT NOT NULL,
    ID_Usuario_Creacion INT,
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (IDCliente) REFERENCES Clientes(ID_Cliente),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

CREATE TABLE Detalle_Facturacion (
    ID_Detalle INT PRIMARY KEY AUTO_INCREMENT,
    ID_Factura INT,
    ID_Producto INT,
    Cantidad DECIMAL(12,2),
    Costo DECIMAL(12,2),
    Total DECIMAL(12,2),
    FOREIGN KEY (ID_Factura) REFERENCES Facturacion(ID_Factura),
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
);

CREATE TABLE Cuentas_Por_Pagar (
    ID_Cuenta INT PRIMARY KEY AUTO_INCREMENT,
    ID_Movimiento INT,
    Fecha DATE,
    ID_Proveedor INT,
    Num_Documento VARCHAR(255),
    Observacion TEXT,
    Fecha_Vencimiento DATE,
    Tipo_Movimiento INT,
    Monto_Movimiento DECIMAL(12,2),
    ID_Empresa INT,
    Saldo_Pendiente DECIMAL(12,2) DEFAULT 0,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Proveedor) REFERENCES Proveedores(ID_Proveedor),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);