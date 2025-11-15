CREATE TABLE `empresa` (
  `ID_Empresa` int NOT NULL AUTO_INCREMENT,
  `Nombre_Empresa` varchar(255) NOT NULL,
  `Direccion` varchar(240) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `RUC` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`ID_Empresa`)
) ENGINE=InnoDB;
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

INSERT INTO `usuarios` VALUES (1,'Admin','scrypt:32768:8:1$YE2ZlcfqKZeVGLJd$ad87b14a145187f6aefa8e9e4c74e89108c49bb66e1bcf9c8417d8b8e9b32abf45424f7a51aaac88d9b843c5974de619de21ed6ea54a1d02c01e0728209bb3b0',1,'ACTIVO','2025-08-16',1);
INSERT INTO `empresa` VALUES (1,'Granja Huevos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U'),(2,'Cerdos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U');
INSERT INTO `roles` VALUES (1,'Administrador'),(2,'Jefe Galera');

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