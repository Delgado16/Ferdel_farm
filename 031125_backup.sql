CREATE DATABASE  IF NOT EXISTS `db_ferdel` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `db_ferdel`;
-- MySQL dump 10.13  Distrib 8.0.43, for Win64 (x86_64)
--
-- Host: localhost    Database: db_ferdel
-- ------------------------------------------------------
-- Server version	9.4.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `bitacora`
--

DROP TABLE IF EXISTS `bitacora`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bitacora`
--

LOCK TABLES `bitacora` WRITE;
/*!40000 ALTER TABLE `bitacora` DISABLE KEYS */;
INSERT INTO `bitacora` VALUES (1,1,'2025-11-03 10:11:54','AUTH','LOGIN_EXITOSO','127.0.0.1'),(2,1,'2025-11-03 10:12:04','USUARIOS','admin_usuarios','127.0.0.1'),(3,1,'2025-11-03 10:12:06','USUARIOS','admin_usuarios','127.0.0.1'),(4,1,'2025-11-03 10:12:09','CLIENTES','admin_clientes','127.0.0.1'),(5,1,'2025-11-03 10:12:10','PROVEEDORES','admin_proveedores','127.0.0.1'),(6,1,'2025-11-03 10:12:14','CLIENTES','admin_clientes','127.0.0.1'),(7,1,'2025-11-03 10:12:15','CLIENTES-EDITAR','admin_editar_cliente','127.0.0.1'),(8,1,'2025-11-03 10:12:17','CLIENTES-EDITAR','admin_editar_cliente','127.0.0.1'),(9,1,'2025-11-03 10:12:17','CLIENTES','admin_clientes','127.0.0.1'),(10,1,'2025-11-03 10:12:18','PROVEEDORES','admin_proveedores','127.0.0.1'),(11,1,'2025-11-03 10:12:21','PROVEEDORES-EDITAR','admin_editar_proveedor','127.0.0.1'),(12,1,'2025-11-03 10:12:24','PROVEEDORES-EDITAR','admin_editar_proveedor','127.0.0.1'),(13,1,'2025-11-03 10:12:24','PROVEEDORES','admin_proveedores','127.0.0.1'),(14,1,'2025-11-03 10:12:28','UNIDADES-MEDIDAS','admin_unidades_medidas','127.0.0.1'),(15,1,'2025-11-03 10:12:29','UNIDAD-MEDIDA-EDITAR','admin_editar_unidad_medida','127.0.0.1'),(16,1,'2025-11-03 10:12:30','UNIDAD-MEDIDA-EDITAR','admin_editar_unidad_medida','127.0.0.1'),(17,1,'2025-11-03 10:12:30','UNIDADES-MEDIDAS','admin_unidades_medidas','127.0.0.1'),(18,1,'2025-11-03 10:46:50','AUTH','LOGIN_EXITOSO','127.0.0.1'),(19,1,'2025-11-03 10:46:53','CATEGORIAS','admin_categorias','127.0.0.1'),(20,1,'2025-11-03 10:47:45','CATEGORIAS','admin_categorias','127.0.0.1'),(21,1,'2025-11-03 10:48:03','AUTH','LOGIN_EXITOSO','127.0.0.1'),(22,1,'2025-11-03 10:48:06','CATEGORIAS','admin_categorias','127.0.0.1'),(23,1,'2025-11-03 10:48:55','AUTH','LOGIN_EXITOSO','127.0.0.1'),(24,1,'2025-11-03 10:48:57','CATEGORIAS','admin_categorias','127.0.0.1');
/*!40000 ALTER TABLE `bitacora` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `categorias_producto`
--

DROP TABLE IF EXISTS `categorias_producto`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `categorias_producto`
--

LOCK TABLES `categorias_producto` WRITE;
/*!40000 ALTER TABLE `categorias_producto` DISABLE KEYS */;
INSERT INTO `categorias_producto` VALUES (1,'Huevos'),(2,'Pollos'),(3,'Gallinas'),(4,'Alimentos'),(5,'Medicamentos'),(6,'Vacunas'),(7,'Material de Empaque'),(8,'Limpieza y Desinfectantes'),(9,'Equipos'),(10,'Servicios');
/*!40000 ALTER TABLE `categorias_producto` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `clientes`
--

DROP TABLE IF EXISTS `clientes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clientes` (
  `ID_Cliente` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `clientes_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `clientes`
--

LOCK TABLES `clientes` WRITE;
/*!40000 ALTER TABLE `clientes` DISABLE KEYS */;
INSERT INTO `clientes` VALUES (1,'Ariel','87456321','Managua, Nicaragua','R526582555SD',1,'ACTIVO','2025-10-27 11:00:45',1),(2,'Fared','87563214','diriomo, Granada','4012563987896Q',1,'ACTIVO','2025-10-29 09:50:51',1),(3,'Ernesto','78965412','Masaya, Masaya','401256398786Q',1,'ACTIVO','2025-10-29 10:46:47',1);
/*!40000 ALTER TABLE `clientes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `empresa`
--

DROP TABLE IF EXISTS `empresa`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `empresa` (
  `ID_Empresa` int NOT NULL AUTO_INCREMENT,
  `Nombre_Empresa` varchar(255) NOT NULL,
  `Direccion` varchar(240) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `RUC` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `empresa`
--

LOCK TABLES `empresa` WRITE;
/*!40000 ALTER TABLE `empresa` DISABLE KEYS */;
INSERT INTO `empresa` VALUES (1,'Granja Huevos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U');
/*!40000 ALTER TABLE `empresa` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `proveedores`
--

DROP TABLE IF EXISTS `proveedores`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `proveedores` (
  `ID_Proveedor` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Proveedor`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `proveedores_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `proveedores_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `proveedores`
--

LOCK TABLES `proveedores` WRITE;
/*!40000 ALTER TABLE `proveedores` DISABLE KEYS */;
INSERT INTO `proveedores` VALUES (1,'Barranca','78965412','Masaya, Masaya','7895542366E',1,'ACTIVO','2025-11-03 09:24:54',1);
/*!40000 ALTER TABLE `proveedores` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `roles`
--

LOCK TABLES `roles` WRITE;
/*!40000 ALTER TABLE `roles` DISABLE KEYS */;
INSERT INTO `roles` VALUES (1,'Administrador'),(2,'Jefe Galera');
/*!40000 ALTER TABLE `roles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `unidades_medida`
--

DROP TABLE IF EXISTS `unidades_medida`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `unidades_medida`
--

LOCK TABLES `unidades_medida` WRITE;
/*!40000 ALTER TABLE `unidades_medida` DISABLE KEYS */;
INSERT INTO `unidades_medida` VALUES (1,'Unidad','UND'),(2,'Kilogramo','KG'),(3,'Gramo','GR'),(4,'Litro','LT'),(5,'Metro','MT'),(6,'Cajilla','CJ'),(7,'Caja','CJA'),(8,'Paquete','PAQ'),(9,'Docena','DOC');
/*!40000 ALTER TABLE `unidades_medida` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios`
--

LOCK TABLES `usuarios` WRITE;
/*!40000 ALTER TABLE `usuarios` DISABLE KEYS */;
INSERT INTO `usuarios` VALUES (1,'Admin','scrypt:32768:8:1$pnCXuiDFWS4ZUVVv$88299d841baa06bf821717fb6b7d9faadff121c441d7b93139928ba6817a66869f31a8af5f95772e2581d01d0aeaa12992cd92caa0221d84bb35bab4d5a0a95f',1,'ACTIVO','2025-08-16',1),(2,'fared','scrypt:32768:8:1$T0AjU1WikbHz4i20$0db146afab1c973dc028fc655242443df63eed395b7c507926d1e761ff552bc7eb7385559652fd37fc4a216e98a5c61309dc337da8c542b6800e35ba062f6466',2,'ACTIVO','2025-10-27',1);
/*!40000 ALTER TABLE `usuarios` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'db_ferdel'
--

--
-- Dumping routines for database 'db_ferdel'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-11-03 10:54:57
