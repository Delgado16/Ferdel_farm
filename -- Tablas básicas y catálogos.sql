-- Tablas básicas y catálogos
CREATE TABLE Metodos_Pago (
    ID_MetodoPago INT PRIMARY KEY AUTO_INCREMENT,
    Nombre VARCHAR(255) NOT NULL
);

CREATE TABLE Unidades_Medida (
    ID_Unidad INT PRIMARY KEY AUTO_INCREMENT,
    Descripcion VARCHAR(255) NOT NULL,
    Abreviatura VARCHAR(50)
);

CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB;

CREATE TABLE Catalogo_Movimientos (
    ID_TipoMovimiento INT PRIMARY KEY AUTO_INCREMENT,
    Descripcion VARCHAR(255),
    Adicion VARCHAR(255),
    Letra VARCHAR(10)
);

CREATE TABLE `bodegas` (
  `ID_Bodega` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Ubicacion` text,
  `Estado` enum('activa','inactiva') DEFAULT 'activa',
  `Fecha_Creacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Actualizacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Bodega`)
) ENGINE=InnoDB;

-- Tablas de seguridad y usuarios
CREATE TABLE roles (
    ID_Rol INT NOT NULL AUTO_INCREMENT,
    Nombre_Rol VARCHAR(255) NOT NULL,
    PRIMARY KEY (ID_Rol)
) ENGINE=InnoDB;

CREATE TABLE empresa (
    ID_Empresa INT NOT NULL AUTO_INCREMENT,
    Nombre_Empresa VARCHAR(255) NOT NULL,
    Direccion VARCHAR(240) DEFAULT NULL,
    Telefono VARCHAR(20) DEFAULT NULL,
    Estado ENUM('Activo','Inactivo') DEFAULT 'Activo',
    RUC VARCHAR(20) DEFAULT NULL,
    PRIMARY KEY (ID_Empresa)
) ENGINE=InnoDB;

CREATE TABLE usuarios (
    ID_Usuario INT NOT NULL AUTO_INCREMENT,
    NombreUsuario VARCHAR(255) NOT NULL,
    Contraseña VARCHAR(255) NOT NULL,
    ID_Rol INT DEFAULT NULL,
    Estado ENUM('ACTIVO','INACTIVO','BLOQUEADO','PENDIENTE') DEFAULT 'ACTIVO',
    Fecha_Creacion DATE DEFAULT (CURDATE()),
    ID_Empresa INT NOT NULL,
    PRIMARY KEY (ID_Usuario),
    UNIQUE KEY NombreUsuario (NombreUsuario),
    KEY ID_Rol (ID_Rol),
    KEY ID_Empresa (ID_Empresa),
    CONSTRAINT usuarios_ibfk_1 FOREIGN KEY (ID_Rol) REFERENCES roles (ID_Rol),
    CONSTRAINT usuarios_ibfk_2 FOREIGN KEY (ID_Empresa) REFERENCES empresa (ID_Empresa)
) ENGINE=InnoDB;

CREATE TABLE bitacora (
    ID_Bitacora INT NOT NULL AUTO_INCREMENT,
    ID_Usuario INT DEFAULT NULL,
    Fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    Modulo VARCHAR(255) DEFAULT NULL,
    Accion VARCHAR(255) DEFAULT NULL,
    IP_Acceso VARCHAR(45) DEFAULT NULL,
    PRIMARY KEY (ID_Bitacora),
    KEY ID_Usuario (ID_Usuario),
    CONSTRAINT bitacora_ibfk_1 FOREIGN KEY (ID_Usuario) REFERENCES usuarios (ID_Usuario)
) ENGINE=InnoDB;

-- Tablas de entidades comerciales
CREATE TABLE Clientes (
    ID_Cliente INT PRIMARY KEY AUTO_INCREMENT,
    Nombre VARCHAR(255) NOT NULL,
    Telefono VARCHAR(50),
    Direccion TEXT,
    RUC_CEDULA VARCHAR(50),
    ID_Empresa INT,
    Estado ENUM('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

CREATE TABLE Proveedores (
    ID_Proveedor INT PRIMARY KEY AUTO_INCREMENT,
    Nombre VARCHAR(255) NOT NULL,
    Telefono VARCHAR(50),
    Direccion TEXT,
    RUC_CEDULA VARCHAR(50),
    ID_Empresa INT,
    Estado ENUM('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
    Fecha_Creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

-- Tablas de productos e inventario
CREATE TABLE Productos (
    ID_Producto INT PRIMARY KEY AUTO_INCREMENT,
    COD_Producto VARCHAR(100),
    Descripcion VARCHAR(255) NOT NULL,
    Unidad_Medida INT,
    Existencias DECIMAL(12,2) DEFAULT 0,
    Estado INT DEFAULT 1,
    ID_Categoria INT,
    Precio_Venta DECIMAL(12,2),
    ID_Empresa INT,
    Fecha_Creacion DATE DEFAULT CURRENT_DATE,
    Usuario_Creador INT,
    Stock_Minimo DECIMAL(12,2) DEFAULT 5,
    FOREIGN KEY (Unidad_Medida) REFERENCES Unidades_Medida(ID_Unidad),
    FOREIGN KEY (ID_Categoria) REFERENCES categorias_producto(ID_Categoria),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (Usuario_Creador) REFERENCES usuarios(ID_Usuario)
);

CREATE TABLE Inventario_Bodega (
    ID_Bodega INT,
    ID_Producto INT,
    Existencias DECIMAL(12,2) DEFAULT 0,
    PRIMARY KEY (ID_Bodega, ID_Producto),
    FOREIGN KEY (ID_Bodega) REFERENCES Bodegas(ID_Bodega),
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
);

-- Tablas de movimientos de inventario
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

-- Tablas de facturación y cuentas por cobrar
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

CREATE TABLE Cuentas_Por_Cobrar (
    ID_Movimiento INT PRIMARY KEY AUTO_INCREMENT,
    Fecha DATE NOT NULL,
    ID_Cliente INT NOT NULL,
    Num_Documento VARCHAR(255) NOT NULL,
    Observacion TEXT,
    Fecha_Vencimiento DATE,
    Tipo_Movimiento INT NOT NULL,
    Monto_Movimiento DECIMAL(12,2) NOT NULL,
    ID_Empresa INT NOT NULL,
    Saldo_Pendiente DECIMAL(12,2),
    ID_Factura INT,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Cliente) REFERENCES Clientes(ID_Cliente),
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Factura) REFERENCES Facturacion(ID_Factura),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

-- Tablas de cuentas por pagar
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

-- Tablas de pagos
CREATE TABLE Pagos_CuentasPagar (
    ID_Pago INT PRIMARY KEY AUTO_INCREMENT,
    ID_Cuenta INT,
    Fecha DATETIME,
    Monto DECIMAL(12,2),
    ID_MetodoPago INT,
    Detalles_Metodo TEXT,
    Comentarios TEXT,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Cuenta) REFERENCES Cuentas_Por_Pagar(ID_Cuenta),
    FOREIGN KEY (ID_MetodoPago) REFERENCES Metodos_Pago(ID_MetodoPago),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

CREATE TABLE Pagos_CuentasCobrar (
    ID_Pago INT PRIMARY KEY AUTO_INCREMENT,
    ID_Movimiento INT NOT NULL,
    Fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Monto DECIMAL(12,2) NOT NULL,
    ID_MetodoPago INT NOT NULL,
    Comentarios TEXT,
    Detalles_Metodo TEXT,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Movimiento) REFERENCES Detalle_Cuentas_Por_Cobrar(ID_Movimiento) ON DELETE CASCADE,
    FOREIGN KEY (ID_MetodoPago) REFERENCES Metodos_Pago(ID_MetodoPago),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

-- Tabla de gastos
CREATE TABLE Gastos (
    ID_Movimiento INT PRIMARY KEY AUTO_INCREMENT,
    Fecha DATE,
    Observacion TEXT,
    Monto DECIMAL(12,2),
    ID_Empresa INT,
    ID_Usuario_Creacion INT,
    FOREIGN KEY (ID_Empresa) REFERENCES empresa(ID_Empresa),
    FOREIGN KEY (ID_Usuario_Creacion) REFERENCES usuarios(ID_Usuario)
);

-- Vista
CREATE VIEW Vista_Compras AS
SELECT 
    mi.ID_Movimiento AS ID_Compra,
    mi.Fecha,
    p.Nombre AS Proveedor,
    mi.N_Factura,
    mi.Observacion,
    SUM(dmi.Costo_Total) AS Total
FROM Movimientos_Inventario mi
JOIN Proveedores p ON p.ID_Proveedor = mi.ID_Proveedor
JOIN Detalle_Movimiento_Inventario dmi ON dmi.ID_Movimiento = mi.ID_Movimiento
WHERE mi.ID_TipoMovimiento = (SELECT ID_TipoMovimiento FROM Catalogo_Movimientos WHERE Descripcion = 'Compra')
GROUP BY mi.ID_Movimiento;

-- Datos básicos iniciales
INSERT INTO roles (Nombre_Rol) VALUES 
('Administrador'),
('Usuario'),
('Vendedor'),
('Almacenista');

INSERT INTO empresa (Nombre_Empresa, Direccion, Telefono, RUC, Estado) VALUES 
('Empresa Principal', 'Dirección Principal', '12345678', '1234567890123', 'Activo');

INSERT INTO Metodos_Pago (Nombre) VALUES 
('Efectivo'),
('Tarjeta de Crédito'),
('Tarjeta de Débito'),
('Transferencia Bancaria'),
('Cheque');

INSERT INTO Catalogo_Movimientos (Descripcion, Adicion, Letra) VALUES 
('Compra', 'Entrada', 'E'),
('Venta', 'Salida', 'S'),
('Ajuste Entrada', 'Entrada', 'E'),
('Ajuste Salida', 'Salida', 'S'),
('Traslado', 'Movimiento Interno', 'T');