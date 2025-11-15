use db_ferdel;

CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB;

CREATE TABLE `usuarios` (
  `ID_Usuario` int NOT NULL AUTO_INCREMENT,
  `NombreUsuario` varchar(255) NOT NULL,
  `Contraseña` varchar(255) NOT NULL,
  `ID_Rol` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO','BLOQUEADO','PENDIENTE') DEFAULT 'ACTIVO',
  `Fecha_Creacion` date DEFAULT (curdate()),
  `ID_Empresa` int NOT NULL,
  PRIMARY KEY (`ID_Usuario`),
  UNIQUE KEY `NombreUsuario` (`NombreUsuario`),
  KEY `ID_Rol` (`ID_Rol`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `usuarios_ibfk_1` FOREIGN KEY (`ID_Rol`) REFERENCES `roles` (`ID_Rol`),
  CONSTRAINT `usuarios_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB;

CREATE TABLE `empresa` (
  `ID_Empresa` int NOT NULL AUTO_INCREMENT,
  `Nombre_Empresa` varchar(255) NOT NULL,
  `Direccion` varchar(240) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `RUC` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`ID_Empresa`)
) ENGINE=InnoDB;

CREATE TABLE `bitacora` (
  `ID_Bitacora` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int DEFAULT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `Modulo` varchar(255) DEFAULT NULL,
  `Accion` varchar(255) DEFAULT NULL,
  `IP_Acceso` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`ID_Bitacora`),
  KEY `ID_Usuario` (`ID_Usuario`),
  CONSTRAINT `bitacora_ibfk_1` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB;

DROP TABLE bitacora;

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
)ENGINE=InnoDB;

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

#unidades de medidas
CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`)
) ENGINE=InnoDB;


INSERT INTO Unidades_Medida (Descripcion, Abreviatura) VALUES 
('Unidad', 'UND'),
('Kilogramo', 'KG'),
('Gramo', 'GR'),
('Litro', 'LT'),
('Metro', 'MT'),
('Cajilla', 'CJ'),
('Caja', 'CJA'),
('Paquete', 'PAQ'),
('Docena', 'DOC');

CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB;

INSERT INTO `categorias_producto` VALUES 
(1,'Huevos'),
(2,'Pollos'),
(3,'Gallinas'),
(4,'Alimentos'),
(5,'Medicamentos'),
(6,'Vacunas'),
(7,'Material de Empaque'),
(8,'Limpieza y Desinfectantes'),
(9,'Equipos'),
(10,'Servicios');