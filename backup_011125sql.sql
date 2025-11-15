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
) ENGINE=InnoDB AUTO_INCREMENT=85 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bitacora`
--

LOCK TABLES `bitacora` WRITE;
/*!40000 ALTER TABLE `bitacora` DISABLE KEYS */;
INSERT INTO `bitacora` VALUES (1,1,'2025-10-25 23:44:51','BITACORA','admin_bitacora','127.0.0.1'),(2,1,'2025-10-27 05:43:04','AUTH','LOGIN_EXITOSO','127.0.0.1'),(3,1,'2025-10-27 05:43:11','BITACORA','admin_bitacora','127.0.0.1'),(4,1,'2025-10-27 05:55:17','AUTH','LOGOUT','127.0.0.1'),(5,1,'2025-10-27 05:55:59','AUTH','LOGIN_EXITOSO','127.0.0.1'),(6,1,'2025-10-27 06:30:02','AUTH','LOGOUT','127.0.0.1'),(7,NULL,'2025-10-27 06:30:09','AUTH','LOGIN_FALLIDO: contraseña incorrecta - Usuario: Admin','127.0.0.1'),(8,1,'2025-10-27 06:30:39','AUTH','LOGIN_EXITOSO','127.0.0.1'),(9,1,'2025-10-27 06:36:19','AUTH','LOGOUT','127.0.0.1'),(10,NULL,'2025-10-27 06:36:29','AUTH','LOGIN_FALLIDO: contraseña no encontrado o inactivo - Usuario: Abel','127.0.0.1'),(11,1,'2025-10-27 06:37:13','AUTH','LOGIN_EXITOSO','127.0.0.1'),(12,1,'2025-10-27 06:37:17','USUARIOS','admin_usuarios','127.0.0.1'),(13,1,'2025-10-27 06:37:50','USUARIOS','CREAR_USUARUI: fared','127.0.0.1'),(14,1,'2025-10-27 06:37:50','USUARIOS','crear_usuario','127.0.0.1'),(15,1,'2025-10-27 06:37:50','USUARIOS','admin_usuarios','127.0.0.1'),(16,1,'2025-10-27 06:49:49','AUTH','LOGOUT','127.0.0.1'),(17,1,'2025-10-27 06:50:01','AUTH','LOGIN_EXITOSO','127.0.0.1'),(18,1,'2025-10-27 06:50:04','AUTH','LOGOUT','127.0.0.1'),(19,2,'2025-10-27 06:50:11','AUTH','LOGIN_EXITOSO','127.0.0.1'),(20,2,'2025-10-27 06:58:24','AUTH','LOGOUT','127.0.0.1'),(21,1,'2025-10-27 06:58:27','AUTH','LOGIN_EXITOSO','127.0.0.1'),(22,2,'2025-10-27 07:02:41','AUTH','LOGIN_EXITOSO','127.0.0.1'),(23,1,'2025-10-31 10:22:08','AUTH','LOGIN_EXITOSO','127.0.0.1'),(24,1,'2025-10-31 10:22:23','CLIENTES','admin_clientes','127.0.0.1'),(25,1,'2025-10-31 10:22:24','CLIENTES','admin_clientes','127.0.0.1'),(26,1,'2025-10-31 11:03:26','CLIENTES','admin_clientes','127.0.0.1'),(27,1,'2025-10-31 11:03:36','CLIENTES','admin_crear_cliente','127.0.0.1'),(28,1,'2025-10-31 11:03:36','CLIENTES','admin_clientes','127.0.0.1'),(29,1,'2025-10-31 11:03:41','CLIENTES','admin_clientes','127.0.0.1'),(30,1,'2025-10-31 11:03:45','CLIENTES','admin_clientes','127.0.0.1'),(31,1,'2025-10-31 11:05:38','CLIENTES','admin_clientes','127.0.0.1'),(32,1,'2025-10-31 11:08:34','CLIENTES','admin_clientes','127.0.0.1'),(33,1,'2025-10-31 11:17:32','CLIENTES','admin_clientes','127.0.0.1'),(34,1,'2025-10-31 11:17:35','CLIENTES','admin_clientes','127.0.0.1'),(35,1,'2025-10-31 11:23:41','AUTH','LOGIN_EXITOSO','127.0.0.1'),(36,1,'2025-10-31 11:26:27','CLIENTES','admin_clientes','127.0.0.1'),(37,1,'2025-10-31 11:27:02','CLIENTES','admin_clientes','127.0.0.1'),(38,1,'2025-10-31 13:18:34','AUTH','LOGIN_EXITOSO','127.0.0.1'),(39,1,'2025-10-31 13:19:12','CLIENTES','admin_clientes','127.0.0.1'),(40,1,'2025-10-31 13:22:28','CLIENTES','admin_clientes','127.0.0.1'),(41,1,'2025-10-31 13:24:57','CLIENTES','admin_clientes','127.0.0.1'),(42,1,'2025-10-31 13:44:09','CLIENTES','admin_clientes','127.0.0.1'),(43,1,'2025-10-31 13:44:10','PROVEEDORES','admin_proveedores','127.0.0.1'),(44,1,'2025-10-31 15:10:58','AUTH','LOGIN_EXITOSO','127.0.0.1'),(45,1,'2025-10-31 15:24:22','CLIENTES','admin_clientes','127.0.0.1'),(46,1,'2025-10-31 15:24:23','CLIENTES','admin_clientes','127.0.0.1'),(47,1,'2025-10-31 15:24:25','CLIENTES','admin_clientes','127.0.0.1'),(48,1,'2025-10-31 15:24:25','CLIENTES','admin_clientes','127.0.0.1'),(49,1,'2025-10-31 15:24:25','CLIENTES','admin_clientes','127.0.0.1'),(50,1,'2025-10-31 15:24:38','CLIENTES','admin_clientes','127.0.0.1'),(51,1,'2025-10-31 15:27:52','PROVEEDORES','admin_proveedores','127.0.0.1'),(52,1,'2025-10-31 15:31:48','PROVEEDORES','admin_proveedores','127.0.0.1'),(53,1,'2025-10-31 15:38:52','PROVEEDORES','admin_proveedores','127.0.0.1'),(54,1,'2025-10-31 15:39:27','CREAR-PROVEEDORES','admin_crear_proveedor','127.0.0.1'),(55,1,'2025-10-31 15:39:27','PROVEEDORES','admin_proveedores','127.0.0.1'),(56,1,'2025-10-31 16:53:36','AUTH','LOGIN_EXITOSO','127.0.0.1'),(57,1,'2025-10-31 16:53:48','CLIENTES','admin_clientes','127.0.0.1'),(58,1,'2025-10-31 16:55:21','CREAR-CLIENTES','admin_crear_cliente','127.0.0.1'),(59,1,'2025-10-31 16:55:21','CLIENTES','admin_clientes','127.0.0.1'),(60,1,'2025-10-31 17:09:18','CLIENTES','admin_clientes','127.0.0.1'),(61,1,'2025-10-31 17:09:34','USUARIOS','admin_usuarios','127.0.0.1'),(62,1,'2025-10-31 17:09:34','CLIENTES','admin_clientes','127.0.0.1'),(63,1,'2025-10-31 17:38:58','CLIENTES','admin_clientes','127.0.0.1'),(64,1,'2025-10-31 22:17:49','AUTH','LOGIN_EXITOSO','127.0.0.1'),(65,1,'2025-10-31 22:18:56','PROVEEDORES','admin_proveedores','127.0.0.1'),(66,1,'2025-10-31 22:23:31','CLIENTES','admin_clientes','127.0.0.1'),(67,1,'2025-10-31 22:25:33','PROVEEDORES','admin_proveedores','127.0.0.1'),(68,1,'2025-10-31 23:24:20','PROVEEDORES','admin_proveedores','127.0.0.1'),(69,1,'2025-10-31 23:24:21','EDITAR-PROVEEDORES','admin_editar_proveedor','127.0.0.1'),(70,1,'2025-10-31 23:24:28','CLIENTES','admin_clientes','127.0.0.1'),(71,1,'2025-10-31 23:24:29','EDITAR-CLIENTES','admin_editar_cliente','127.0.0.1'),(72,1,'2025-10-31 23:24:38','PROVEEDORES','admin_proveedores','127.0.0.1'),(73,1,'2025-10-31 23:24:40','EDITAR-PROVEEDORES','admin_editar_proveedor','127.0.0.1'),(74,1,'2025-10-31 23:26:00','EDITAR-PROVEEDORES','admin_editar_proveedor','127.0.0.1'),(75,1,'2025-10-31 23:26:01','PROVEEDORES','admin_proveedores','127.0.0.1'),(76,1,'2025-10-31 23:26:19','CLIENTES','admin_clientes','127.0.0.1'),(77,1,'2025-10-31 23:26:22','EDITAR-CLIENTES','admin_editar_cliente','127.0.0.1'),(78,1,'2025-10-31 23:26:28','EDITAR-CLIENTES','admin_editar_cliente','127.0.0.1'),(79,1,'2025-10-31 23:26:29','CLIENTES','admin_clientes','127.0.0.1'),(80,1,'2025-10-31 23:26:37','PROVEEDORES','admin_proveedores','127.0.0.1'),(81,1,'2025-11-01 08:38:34','AUTH','LOGIN_EXITOSO','127.0.0.1'),(82,1,'2025-11-01 08:39:31','PROVEEDORES','admin_proveedores','127.0.0.1'),(83,1,'2025-11-01 08:39:39','EDITAR-PROVEEDORES','admin_editar_proveedor','127.0.0.1'),(84,1,'2025-11-01 08:39:57','PROVEEDORES','admin_proveedores','127.0.0.1');
/*!40000 ALTER TABLE `bitacora` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bodegas`
--

DROP TABLE IF EXISTS `bodegas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bodegas` (
  `ID_Bodega` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Ubicacion` text,
  PRIMARY KEY (`ID_Bodega`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bodegas`
--

LOCK TABLES `bodegas` WRITE;
/*!40000 ALTER TABLE `bodegas` DISABLE KEYS */;
/*!40000 ALTER TABLE `bodegas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `catalogo_movimientos`
--

DROP TABLE IF EXISTS `catalogo_movimientos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `catalogo_movimientos` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `catalogo_movimientos`
--

LOCK TABLES `catalogo_movimientos` WRITE;
/*!40000 ALTER TABLE `catalogo_movimientos` DISABLE KEYS */;
/*!40000 ALTER TABLE `catalogo_movimientos` ENABLE KEYS */;
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `clientes`
--

LOCK TABLES `clientes` WRITE;
/*!40000 ALTER TABLE `clientes` DISABLE KEYS */;
INSERT INTO `clientes` VALUES (1,'Jorges','78963251','Ticuantepe, Managua','R526582555SD',1,'ACTIVO','2025-10-31 11:03:35',1),(2,'Fares','85809865','bo.17 de octubreFrente a la casa de la mujer','401-160503-1006T',1,'ACTIVO','2025-10-31 16:55:21',1);
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `empresa`
--

LOCK TABLES `empresa` WRITE;
/*!40000 ALTER TABLE `empresa` DISABLE KEYS */;
INSERT INTO `empresa` VALUES (1,'Granja Huevos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U'),(2,'Cerdos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U');
/*!40000 ALTER TABLE `empresa` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `metodos_pago`
--

DROP TABLE IF EXISTS `metodos_pago`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `metodos_pago` (
  `ID_MetodoPago` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_MetodoPago`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `metodos_pago`
--

LOCK TABLES `metodos_pago` WRITE;
/*!40000 ALTER TABLE `metodos_pago` DISABLE KEYS */;
/*!40000 ALTER TABLE `metodos_pago` ENABLE KEYS */;
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
INSERT INTO `proveedores` VALUES (1,'Huevos Barrancas','89562374','Nindiri, Masaya','E78522CS5544',1,'ACTIVO','2025-10-31 15:39:27',1);
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `unidades_medida`
--

LOCK TABLES `unidades_medida` WRITE;
/*!40000 ALTER TABLE `unidades_medida` DISABLE KEYS */;
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
INSERT INTO `usuarios` VALUES (1,'Admin','scrypt:32768:8:1$YE2ZlcfqKZeVGLJd$ad87b14a145187f6aefa8e9e4c74e89108c49bb66e1bcf9c8417d8b8e9b32abf45424f7a51aaac88d9b843c5974de619de21ed6ea54a1d02c01e0728209bb3b0',1,'ACTIVO','2025-08-16',1),(2,'fared','scrypt:32768:8:1$T0AjU1WikbHz4i20$0db146afab1c973dc028fc655242443df63eed395b7c507926d1e761ff552bc7eb7385559652fd37fc4a216e98a5c61309dc337da8c542b6800e35ba062f6466',2,'ACTIVO','2025-10-27',1);
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

-- Dump completed on 2025-11-01 11:44:00
