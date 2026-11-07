package com.example.myapplication.data.gnss.udp

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.IOException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.SocketTimeoutException

internal const val EXTERNAL_UDP_PORT = 9090

internal enum class ExternalUdpStage {
    OFF, STARTING, LISTENING, RECEIVING, STALE, UNAVAILABLE
}

internal data class ExternalUdpStatus(
    val stage: ExternalUdpStage = ExternalUdpStage.OFF,
    val port: Int = EXTERNAL_UDP_PORT,
    val datagramsReceived: Long = 0,
    val nmeaReceived: Long = 0,
    val lastSentenceType: String? = null
)

internal class ExternalUdpMonitor(
    private val port: Int = EXTERNAL_UDP_PORT,
    private val staleAfterMillis: Long = 5_000L,
    private val elapsedMillis: () -> Long
) {
    // A rapid mode switch must wait for the previous socket to close before rebinding.
    private val socketLock = Mutex()

    fun observe(): Flow<ExternalUdpStatus> = flow {
        socketLock.withLock {
            DatagramSocket(port).use { socket ->
                socket.soTimeout = 250
                val packet = DatagramPacket(ByteArray(MAX_DATAGRAM_BYTES + 1), MAX_DATAGRAM_BYTES + 1)
                var lastNmeaElapsed = 0L
                var status = ExternalUdpStatus(ExternalUdpStage.LISTENING, socket.localPort)
                emit(status)

                while (currentCoroutineContext().isActive) {
                    val previous = status
                    try {
                        packet.length = packet.data.size
                        socket.receive(packet)
                        status = status.copy(datagramsReceived = status.datagramsReceived + 1)
                        val type = if (packet.length <= MAX_DATAGRAM_BYTES) {
                            checkedNmeaType(String(packet.data, packet.offset, packet.length, Charsets.US_ASCII))
                        } else {
                            null
                        }
                        if (type != null) {
                            lastNmeaElapsed = elapsedMillis()
                            status = status.copy(
                                stage = ExternalUdpStage.RECEIVING,
                                nmeaReceived = status.nmeaReceived + 1,
                                lastSentenceType = type
                            )
                        }
                    } catch (_: SocketTimeoutException) {
                        // Wake up periodically to check for cancellation and stale telemetry.
                    }

                    if (status.stage == ExternalUdpStage.RECEIVING &&
                        elapsedMillis() - lastNmeaElapsed >= staleAfterMillis
                    ) {
                        status = status.copy(stage = ExternalUdpStage.STALE)
                    }
                    if (status != previous) emit(status)
                }
            }
        }
    }.catch { cause ->
        if (cause !is IOException && cause !is SecurityException) throw cause
        emit(ExternalUdpStatus(ExternalUdpStage.UNAVAILABLE, port))
    }.flowOn(Dispatchers.IO).conflate()

    private companion object {
        const val MAX_DATAGRAM_BYTES = 1_024
    }
}

private val supportedNmeaTypes = setOf("GGA", "GNS", "GSA", "GSV", "RMC", "GLL", "VTG", "GST", "ZDA")

internal fun checkedNmeaType(datagram: String): String? {
    val sentence = datagram.trimEnd('\r', '\n')
    val checksumIndex = sentence.length - 3
    if (checksumIndex <= 7 || sentence[0] != '$' || sentence[6] != ',' || sentence[checksumIndex] != '*') {
        return null
    }
    if (sentence[1] !in 'A'..'Z' || sentence[2] !in 'A'..'Z') return null
    val type = sentence.substring(3, 6)
    if (type !in supportedNmeaTypes) return null

    val firstDigit = sentence[checksumIndex + 1].digitToIntOrNull(16) ?: return null
    val secondDigit = sentence[checksumIndex + 2].digitToIntOrNull(16) ?: return null
    val expected = firstDigit * 16 + secondDigit
    var actual = 0
    for (index in 1 until checksumIndex) {
        val character = sentence[index]
        if (character !in ' '..'~' || character == '*' || character == '$') return null
        actual = actual xor character.code
    }
    return type.takeIf { actual == expected }
}
